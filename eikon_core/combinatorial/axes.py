"""Axes configuration loading and validation for combinatorial engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AxisOption:
    """A single option within an axis."""

    name: str
    description: str = ""
    overrides: dict[str, str] = field(default_factory=dict)
    data_attrs: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "name": self.name,
            "description": self.description,
            "overrides": dict(self.overrides),
            "data_attrs": dict(self.data_attrs),
        }


@dataclass(frozen=True)
class Axis:
    """A named axis of variation."""

    name: str
    label: str = ""
    axis_type: str = "enum"
    options: tuple[AxisOption, ...] = field(default_factory=tuple)

    def get_option(self, option_name: str) -> AxisOption | None:
        """Get an option by name."""
        for opt in self.options:
            if opt.name == option_name:
                return opt
        return None

    def option_names(self) -> list[str]:
        """Get list of all option names."""
        return [opt.name for opt in self.options]

    def as_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "name": self.name,
            "label": self.label,
            "type": self.axis_type,
            "options": [opt.as_dict() for opt in self.options],
        }


@dataclass(frozen=True)
class AxesConfig:
    """Complete axes configuration."""

    axes: dict[str, Axis] = field(default_factory=dict)

    def get_axis(self, axis_name: str) -> Axis | None:
        """Get an axis by name."""
        return self.axes.get(axis_name)

    def axis_names(self) -> list[str]:
        """Get list of all axis names."""
        return sorted(self.axes.keys())

    def validate_combination(self, combination: dict[str, str]) -> None:
        """Validate a combination dict against this config.

        Raises ValueError if any axis or option is invalid.
        """
        for axis_name, option_name in combination.items():
            axis = self.get_axis(axis_name)
            if axis is None:
                raise ValueError(f"Unknown axis: {axis_name}")
            if axis.get_option(option_name) is None:
                raise ValueError(
                    f"Unknown option '{option_name}' for axis '{axis_name}'. "
                    f"Valid options: {axis.option_names()}"
                )

    def as_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {"axes": {name: axis.as_dict() for name, axis in self.axes.items()}}


def load_axes_config(config_path: Path) -> AxesConfig:
    """Load axes configuration from JSON file.

    Args:
        config_path: Path to axes.json config file

    Returns:
        AxesConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
        json.JSONDecodeError: If JSON is malformed
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Axes config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)

    axes_dict = {}
    axes_data = data.get("axes", {})

    for axis_name, axis_spec in axes_data.items():
        options_data = axis_spec.get("options", {})
        options = []

        for opt_name, opt_spec in options_data.items():
            option = AxisOption(
                name=opt_name,
                description=opt_spec.get("description", ""),
                overrides=dict(opt_spec.get("overrides", {})),
                data_attrs=dict(opt_spec.get("data_attrs", {})),
            )
            options.append(option)

        axis = Axis(
            name=axis_name,
            label=axis_spec.get("label", axis_name),
            axis_type=axis_spec.get("type", "enum"),
            options=tuple(options),
        )
        axes_dict[axis_name] = axis

    return AxesConfig(axes=axes_dict)


def validate_axes_config(config: AxesConfig) -> None:
    """Validate axes configuration for consistency.

    Raises ValueError if configuration is invalid.
    """
    if not config.axes:
        raise ValueError("AxesConfig must have at least one axis")

    for axis in config.axes.values():
        if not axis.options:
            raise ValueError(f"Axis '{axis.name}' must have at least one option")
        if not axis.name:
            raise ValueError("Axis name cannot be empty")
        if not all(opt.name for opt in axis.options):
            raise ValueError(f"All options in axis '{axis.name}' must have names")
