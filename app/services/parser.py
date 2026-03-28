"""Parse ClinicalTrials.gov API v2 study data into flat schema dicts."""

import datetime
import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class ParsedTrial(TypedDict):
    trial_id: str
    title: str
    phase: str | None
    status: str
    sponsor_name: str
    interventions: list[dict[str, object]] | None
    primary_outcomes: list[dict[str, object]] | None
    secondary_outcomes: list[dict[str, object]] | None
    start_date: datetime.date | None
    completion_date: datetime.date | None
    locations: list[dict[str, object]] | None
    enrollment_number: int | None
    raw_data: dict[str, object]


def parse_date(date_string: str | None) -> datetime.date | None:
    """Parse CT.gov date strings which come in multiple formats.

    Handles:
        - "2018-11-29" (ISO 8601 full date)
        - "2015-10" (year-month only, returns 1st of month)
        - "January 2024" (month name and year)
        - "January 15, 2024" (full text date)
        - None or empty string (returns None)
    """
    if not date_string or not date_string.strip():
        return None

    date_string = date_string.strip()

    # Try ISO 8601 full date: "2018-11-29"
    try:
        return datetime.date.fromisoformat(date_string)
    except ValueError:
        pass

    # Try year-month: "2015-10"
    try:
        dt = datetime.datetime.strptime(date_string, "%Y-%m")
        return dt.date()
    except ValueError:
        pass

    # Try "Month Year": "January 2024"
    try:
        dt = datetime.datetime.strptime(date_string, "%B %Y")
        return dt.date()
    except ValueError:
        pass

    # Try "Month Day, Year": "January 15, 2024"
    try:
        dt = datetime.datetime.strptime(date_string, "%B %d, %Y")
        return dt.date()
    except ValueError:
        pass

    logger.warning("Could not parse date: %r", date_string)
    return None


def _safe_get(data: dict[str, object], *keys: str) -> object:
    """Safely navigate nested dicts. Returns None if any key is missing or value is None."""
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)  # type: ignore[union-attr]
        if current is None:
            return None
    return current


def _ensure_dict(val: object) -> dict[str, object]:
    """Return val if it's a dict, otherwise return empty dict."""
    return val if isinstance(val, dict) else {}


def _parse_list_of_dicts(items: object) -> list[dict[str, object]] | None:
    """Extract a list of dicts from a potentially None/non-list value."""
    if not isinstance(items, list) or len(items) == 0:
        return None
    return [item for item in items if isinstance(item, dict)] or None


def parse_study(study: dict[str, object]) -> ParsedTrial:
    """Map a CT.gov API v2 study object to our schema.

    The study object has deeply nested data under protocolSection
    with various modules. Each module may be absent or None.
    """
    protocol = _ensure_dict(study.get("protocolSection", {}))

    id_mod = _ensure_dict(protocol.get("identificationModule", {}))
    status_mod = _ensure_dict(protocol.get("statusModule", {}))
    design_mod = _ensure_dict(protocol.get("designModule", {}))
    sponsor_mod = _ensure_dict(protocol.get("sponsorCollaboratorsModule", {}))
    arms_mod = _ensure_dict(protocol.get("armsInterventionsModule", {}))
    outcomes_mod = _ensure_dict(protocol.get("outcomesModule", {}))
    contacts_mod = _ensure_dict(protocol.get("contactsLocationsModule", {}))

    # trial_id and title (required)
    trial_id = str(id_mod.get("nctId", "UNKNOWN"))
    title = str(id_mod.get("briefTitle", ""))

    # phase: list like ["PHASE2"], take first
    phases = design_mod.get("phases") or []
    if not isinstance(phases, list):
        phases = []
    phase = str(phases[0]) if phases else None

    # status
    status = str(status_mod.get("overallStatus", "UNKNOWN"))

    # sponsor
    lead_sponsor = _ensure_dict(sponsor_mod.get("leadSponsor", {}))
    sponsor_name = str(lead_sponsor.get("name", "Unknown"))

    # interventions: store full array of dicts
    interventions = _parse_list_of_dicts(arms_mod.get("interventions"))

    # primary outcomes: store full array of dicts
    primary_outcomes = _parse_list_of_dicts(outcomes_mod.get("primaryOutcomes"))

    # secondary outcomes: store full array of dicts
    secondary_outcomes = _parse_list_of_dicts(outcomes_mod.get("secondaryOutcomes"))

    # dates
    start_date_struct = _ensure_dict(status_mod.get("startDateStruct", {}))
    start_date_str = start_date_struct.get("date")
    start_date = parse_date(str(start_date_str) if start_date_str is not None else None)

    completion_date_struct = _ensure_dict(status_mod.get("completionDateStruct", {}))
    completion_date_str = completion_date_struct.get("date")
    completion_date = parse_date(str(completion_date_str) if completion_date_str is not None else None)

    # locations: store full array of dicts
    locations = _parse_list_of_dicts(contacts_mod.get("locations"))

    # enrollment
    enrollment_info = _ensure_dict(design_mod.get("enrollmentInfo", {}))
    enrollment_count = enrollment_info.get("count")
    enrollment_number: int | None = None
    if enrollment_count is not None:
        try:
            enrollment_number = int(enrollment_count)
        except (ValueError, TypeError):
            enrollment_number = None

    return ParsedTrial(
        trial_id=trial_id,
        title=title,
        phase=phase,
        status=status,
        sponsor_name=sponsor_name,
        interventions=interventions,
        primary_outcomes=primary_outcomes,
        secondary_outcomes=secondary_outcomes,
        start_date=start_date,
        completion_date=completion_date,
        locations=locations,
        enrollment_number=enrollment_number,
        raw_data=study,  # type: ignore[typeddict-item]
    )
