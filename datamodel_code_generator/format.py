from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence
from warnings import warn

import black
import isort
import toml

from datamodel_code_generator.util import cached_property


class PythonVersion(Enum):
    PY_36 = '3.6'
    PY_37 = '3.7'
    PY_38 = '3.8'
    PY_39 = '3.9'
    PY_310 = '3.10'
    PY_311 = '3.11'
    PY_312 = '3.12'

    @cached_property
    def _is_py_38_or_later(self) -> bool:  # pragma: no cover
        return self.value not in {self.PY_36.value, self.PY_37.value}  # type: ignore

    @cached_property
    def _is_py_39_or_later(self) -> bool:  # pragma: no cover
        return self.value not in {self.PY_36.value, self.PY_37.value, self.PY_38.value}  # type: ignore

    @cached_property
    def _is_py_310_or_later(self) -> bool:  # pragma: no cover
        return self.value not in {self.PY_36.value, self.PY_37.value, self.PY_38.value, self.PY_39.value}  # type: ignore

    @cached_property
    def _is_py_311_or_later(self) -> bool:  # pragma: no cover
        return self.value not in {self.PY_36.value, self.PY_37.value, self.PY_38.value, self.PY_39.value, self.PY_310.value}  # type: ignore

    @property
    def has_literal_type(self) -> bool:
        return self._is_py_38_or_later

    @property
    def has_union_operator(self) -> bool:  # pragma: no cover
        return self._is_py_310_or_later

    @property
    def has_annotated_type(self) -> bool:
        return self._is_py_39_or_later

    @property
    def has_typed_dict(self) -> bool:
        return self._is_py_38_or_later

    @property
    def has_typed_dict_non_required(self) -> bool:
        return self._is_py_311_or_later


if TYPE_CHECKING:

    class _TargetVersion(Enum):
        ...

    BLACK_PYTHON_VERSION: Dict[PythonVersion, _TargetVersion]
else:
    BLACK_PYTHON_VERSION: Dict[PythonVersion, black.TargetVersion] = {
        v: getattr(black.TargetVersion, f'PY{v.name.split("_")[-1]}')
        for v in PythonVersion
        if hasattr(black.TargetVersion, f'PY{v.name.split("_")[-1]}')
    }


def is_supported_in_black(python_version: PythonVersion) -> bool:  # pragma: no cover
    return python_version in BLACK_PYTHON_VERSION


def black_find_project_root(sources: Sequence[Path]) -> Path:
    if TYPE_CHECKING:
        from typing import Iterable, Tuple, Union

        def _find_project_root(
            srcs: Union[Sequence[str], Iterable[str]]
        ) -> Union[Tuple[Path, str], Path]:
            ...

    else:
        from black import find_project_root as _find_project_root
    project_root = _find_project_root(tuple(str(s) for s in sources))
    if isinstance(project_root, tuple):
        return project_root[0]
    else:  # pragma: no cover
        return project_root


class CodeFormatter:
    def __init__(
        self,
        python_version: PythonVersion,
        settings_path: Optional[Path] = None,
        wrap_string_literal: Optional[bool] = None,
        skip_string_normalization: bool = True,
        known_third_party: Optional[List[str]] = None,
    ) -> None:
        if not settings_path:
            settings_path = Path().resolve()

        root = black_find_project_root((settings_path,))
        path = root / 'pyproject.toml'
        if path.is_file():
            value = str(path)
            pyproject_toml = toml.load(value)
            config = pyproject_toml.get('tool', {}).get('black', {})
        else:
            config = {}

        black_kwargs: Dict[str, Any] = {}
        if wrap_string_literal is not None:
            experimental_string_processing = wrap_string_literal
        else:
            experimental_string_processing = config.get(
                'experimental-string-processing'
            )

        if experimental_string_processing is not None:  # pragma: no cover
            if black.__version__.startswith('19.'):  # type: ignore
                warn(
                    f"black doesn't support `experimental-string-processing` option"  # type: ignore
                    f' for wrapping string literal in {black.__version__}'
                )
            else:
                black_kwargs[
                    'experimental_string_processing'
                ] = experimental_string_processing

        if TYPE_CHECKING:
            self.black_mode: black.FileMode
        else:
            self.black_mode = black.FileMode(
                target_versions={BLACK_PYTHON_VERSION[python_version]},
                line_length=config.get('line-length', black.DEFAULT_LINE_LENGTH),
                string_normalization=not skip_string_normalization
                or not config.get('skip-string-normalization', True),
                **black_kwargs,
            )

        self.settings_path: str = str(settings_path)

        self.isort_config_kwargs: Dict[str, Any] = {}
        if known_third_party:
            self.isort_config_kwargs['known_third_party'] = known_third_party

        if isort.__version__.startswith('4.'):
            self.isort_config = None
        else:
            self.isort_config = isort.Config(
                settings_path=self.settings_path, **self.isort_config_kwargs
            )

    def format_code(
        self,
        code: str,
    ) -> str:
        code = self.apply_isort(code)
        code = self.apply_black(code)
        return code

    def apply_black(self, code: str) -> str:
        return black.format_str(
            code,
            mode=self.black_mode,
        )

    if TYPE_CHECKING:

        def apply_isort(self, code: str) -> str:
            ...

    else:
        if isort.__version__.startswith('4.'):

            def apply_isort(self, code: str) -> str:
                return isort.SortImports(
                    file_contents=code,
                    settings_path=self.settings_path,
                    **self.isort_config_kwargs,
                ).output

        else:

            def apply_isort(self, code: str) -> str:
                return isort.code(code, config=self.isort_config)
