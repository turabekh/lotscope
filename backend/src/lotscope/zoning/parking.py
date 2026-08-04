from dataclasses import dataclass

DwellingUse = str

CHAPTER_14_800_VERSION = "title14-ch14-800-2026-06"
CHAPTER_14_800_SOURCE = (
    "Philadelphia Code Chapter 14-800 (Parking and Loading), § 14-802 Motor Vehicle Parking "
    "Ratios: Tables 14-802-1, 14-802-2, 14-802-3"
)

_DWELLING_USES: tuple[str, ...] = ("single_family", "two_family", "multi_family")


@dataclass(frozen=True)
class ParkingRequirement:
    spaces: int
    per_units: int
    table: str


_RESIDENTIAL_TABLE = "Table 14-802-1"
_COMMERCIAL_TABLE = "Table 14-802-2"
_INDUSTRIAL_TABLE = "Table 14-802-3"


def _uniform(spaces: int, per_units: int, table: str) -> dict[str, ParkingRequirement]:
    return {use: ParkingRequirement(spaces, per_units, table) for use in _DWELLING_USES}


_ONE_PER_UNIT = _uniform(1, 1, _RESIDENTIAL_TABLE)
_NONE_RESIDENTIAL = _uniform(0, 1, _RESIDENTIAL_TABLE)
_HIGHER_DENSITY_RESIDENTIAL = {
    "single_family": ParkingRequirement(0, 1, _RESIDENTIAL_TABLE),
    "two_family": ParkingRequirement(1, 2, _RESIDENTIAL_TABLE),
    "multi_family": ParkingRequirement(3, 10, _RESIDENTIAL_TABLE),
}
_NONE_COMMERCIAL = _uniform(0, 1, _COMMERCIAL_TABLE)
_CMX3 = _uniform(3, 10, _COMMERCIAL_TABLE)
_IRMX = _uniform(3, 10, _INDUSTRIAL_TABLE)
_INDUSTRIAL_HALF = _uniform(1, 2, _INDUSTRIAL_TABLE)

PHL_PARKING_REQUIREMENTS: dict[str, dict[str, ParkingRequirement]] = {
    "RSD-1": _ONE_PER_UNIT,
    "RSD-2": _ONE_PER_UNIT,
    "RSD-3": _ONE_PER_UNIT,
    "RSA-1": _ONE_PER_UNIT,
    "RSA-2": _ONE_PER_UNIT,
    "RSA-3": _ONE_PER_UNIT,
    "RTA-1": _ONE_PER_UNIT,
    "RMX-1": _ONE_PER_UNIT,
    "RSA-4": _NONE_RESIDENTIAL,
    "RSA-5": _NONE_RESIDENTIAL,
    "RSA-6": _NONE_RESIDENTIAL,
    "RTA-2": _NONE_RESIDENTIAL,
    "RM-1": _NONE_RESIDENTIAL,
    "RM-2": _HIGHER_DENSITY_RESIDENTIAL,
    "RM-3": _HIGHER_DENSITY_RESIDENTIAL,
    "RM-4": _HIGHER_DENSITY_RESIDENTIAL,
    "RMX-2": _HIGHER_DENSITY_RESIDENTIAL,
    "RMX-3": _HIGHER_DENSITY_RESIDENTIAL,
    "CMX-2": _NONE_COMMERCIAL,
    "CMX-2.5": _NONE_COMMERCIAL,
    "CMX-3": _CMX3,
    "CMX-4": _NONE_COMMERCIAL,
    "CMX-5": _NONE_COMMERCIAL,
    "IRMX": _IRMX,
    "ICMX": _INDUSTRIAL_HALF,
}

SECTION_GOVERNED_DISTRICTS: dict[str, str] = {
    "CMX-1": "§ 14-802(7)(a)",
    "CA-1": "§ 14-802(7)(b)",
    "CA-2": "§ 14-802(7)(b)",
}

_HYPHENLESS = {code.replace("-", "").replace(".", ""): code for code in PHL_PARKING_REQUIREMENTS}
_HYPHENLESS_SECTION = {code.replace("-", ""): code for code in SECTION_GOVERNED_DISTRICTS}


def _canonical(district_code: str) -> str | None:
    if district_code in PHL_PARKING_REQUIREMENTS:
        return district_code
    return _HYPHENLESS.get(district_code.replace("-", "").replace(".", "").upper())


def governing_section(district_code: str) -> str | None:
    if district_code in SECTION_GOVERNED_DISTRICTS:
        return SECTION_GOVERNED_DISTRICTS[district_code]
    canonical = _HYPHENLESS_SECTION.get(district_code.replace("-", "").upper())
    return SECTION_GOVERNED_DISTRICTS.get(canonical) if canonical else None


def parking_requirement(district_code: str, dwelling_use: DwellingUse) -> ParkingRequirement | None:
    canonical = _canonical(district_code)
    if canonical is None:
        return None
    return PHL_PARKING_REQUIREMENTS[canonical].get(dwelling_use)


def requirement_phrase(requirement: ParkingRequirement) -> str:
    if requirement.spaces == 0:
        return "no off-street parking"
    space_word = "space" if requirement.spaces == 1 else "spaces"
    if requirement.per_units == 1:
        return f"{requirement.spaces} off-street {space_word} per dwelling unit"
    return (
        f"{requirement.spaces} off-street {space_word} per {requirement.per_units} dwelling units"
    )


def required_spaces(requirement: ParkingRequirement, units: int) -> int | None:
    total = requirement.spaces * units
    if total % requirement.per_units != 0:
        return None
    return total // requirement.per_units
