"""Profile identity service and revision CLI for authored profiles."""

from __future__ import annotations

import argparse
from copy import deepcopy
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any

from .identity import new_profile_id, profile_version
from .persistence import ConfigurationStore
from .profile_validation import profile_payload, validate_profile_configuration


class ProfileIdentityService:
    """Create profile IDs and versions only when an author changes a profile."""

    def create(self, definition: Mapping[str, Any]) -> dict[str, Any]:
        """Create a profile with a new stable ID and its first version."""
        return self.revise(new_profile_id(), definition)

    def revise(
        self,
        profile_id: str,
        definition: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return an authored revision with the same ID and derived version."""
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")
        if not isinstance(definition, Mapping):
            raise ValueError("Profile definition must be an object")

        profile = deepcopy(dict(definition))
        profile["profile_id"] = profile_id
        profile.pop("profile_version", None)
        profile["profile_version"] = profile_version(profile)
        return profile


def revise_profile_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Revise, validate, and save a manually edited profile JSON file."""
    source = Path(input_path)
    destination = Path(output_path)
    if destination.exists() and destination != source and not overwrite:
        raise FileExistsError(
            f"Refusing to overwrite existing output file: {destination}. "
            "Choose another path, use --overwrite, or use --in-place."
        )

    store = ConfigurationStore()
    edited_definition = store.load_test_configuration(source)
    profile_id = edited_definition.get("profile_id")
    revised = ProfileIdentityService().revise(profile_id, edited_definition)
    validated = validate_profile_configuration(revised)
    return store.save_test_configuration(profile_payload(validated), destination)


def create_profile_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Create, validate, and save a new profile from a hand-authored draft."""
    source = Path(input_path)
    destination = Path(output_path)
    if destination.exists() and destination != source and not overwrite:
        raise FileExistsError(
            f"Refusing to overwrite existing output file: {destination}. "
            "Choose another path, use --overwrite, or use --in-place."
        )

    store = ConfigurationStore()
    draft_definition = store.load_test_configuration(source)
    unexpected_identity = sorted(
        {"profile_id", "profile_version"} & draft_definition.keys()
    )
    if unexpected_identity:
        raise ValueError(
            "New profile drafts must not contain " + ", ".join(unexpected_identity)
        )
    created = ProfileIdentityService().create(draft_definition)
    validated = validate_profile_configuration(created)
    return store.save_test_configuration(profile_payload(validated), destination)


def _default_revised_path(input_path: Path) -> Path:
    """Return a sibling path that preserves the hand-edited source file."""
    return input_path.with_name(f"{input_path.stem}.revised{input_path.suffix}")


def main(arguments: list[str] | None = None) -> int:
    """Run the command-line interface for trained profile authors."""
    parser = argparse.ArgumentParser(
        description="Create or revise manually authored battery-profile JSON files.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    create_parser = subcommands.add_parser(
        "create",
        help="create profile_id and profile_version for a new draft",
    )
    create_parser.add_argument("input", type=Path, help="hand-authored profile draft JSON file")
    create_output_group = create_parser.add_mutually_exclusive_group()
    create_output_group.add_argument("--output", type=Path, help="path for created JSON")
    create_output_group.add_argument(
        "--in-place",
        action="store_true",
        help="replace the input draft after successful validation",
    )
    create_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="permit replacement of an existing --output file",
    )
    revise_parser = subcommands.add_parser(
        "revise",
        help="preserve profile_id, calculate profile_version, and validate",
    )
    revise_parser.add_argument("input", type=Path, help="manually edited profile JSON file")
    output_group = revise_parser.add_mutually_exclusive_group()
    output_group.add_argument("--output", type=Path, help="path for revised JSON")
    output_group.add_argument(
        "--in-place",
        action="store_true",
        help="replace the input file after successful validation",
    )
    revise_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="permit replacement of an existing --output file",
    )

    options = parser.parse_args(arguments)
    if options.command not in {"create", "revise"}:  # pragma: no cover - argparse enforces choices.
        parser.error(f"Unsupported command: {options.command}")

    source = options.input
    destination = source if options.in_place else options.output or _default_revised_path(source)
    try:
        profile_file_action = (
            create_profile_file if options.command == "create" else revise_profile_file
        )
        written_path = profile_file_action(
            source,
            destination,
            overwrite=options.overwrite or options.in_place,
        )
    except (OSError, ValueError) as error:
        print(f"Profile authoring failed: {error}", file=sys.stderr)
        return 2

    print(f"{options.command.title()}d profile written to {written_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
