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
    intervention_type: str | None
    intervention_name: str | None
    primary_outcome_description: str | None
    primary_outcome_measure: str | None
    start_date: datetime.date | None
    completion_date: datetime.date | None
    location_country: str | None
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


def _first_from_list(data: dict[str, object], *keys: str, field: str | None = None) -> object:
    """Navigate to a nested list, get first element, optionally extract a field."""
    items = _safe_get(data, *keys)
    if not isinstance(items, list) or len(items) == 0:
        return None
    first = items[0]
    if field is not None and isinstance(first, dict):
        return first.get(field)
    return first


def parse_study(study: dict[str, object]) -> ParsedTrial:
    """Map a CT.gov API v2 study object to our flat schema.

    The study object has deeply nested data under protocolSection
    with various modules. Each module may be absent or None.
    """
    protocol = study.get("protocolSection", {}) or {}
    if not isinstance(protocol, dict):
        protocol = {}

    id_mod = protocol.get("identificationModule", {}) or {}
    status_mod = protocol.get("statusModule", {}) or {}
    design_mod = protocol.get("designModule", {}) or {}
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {}) or {}
    arms_mod = protocol.get("armsInterventionsModule", {}) or {}
    outcomes_mod = protocol.get("outcomesModule", {}) or {}
    contacts_mod = protocol.get("contactsLocationsModule", {}) or {}

    # Ensure dicts
    if not isinstance(id_mod, dict):
        id_mod = {}
    if not isinstance(status_mod, dict):
        status_mod = {}
    if not isinstance(design_mod, dict):
        design_mod = {}
    if not isinstance(sponsor_mod, dict):
        sponsor_mod = {}
    if not isinstance(arms_mod, dict):
        arms_mod = {}
    if not isinstance(outcomes_mod, dict):
        outcomes_mod = {}
    if not isinstance(contacts_mod, dict):
        contacts_mod = {}

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
    lead_sponsor = sponsor_mod.get("leadSponsor") or {}
    if not isinstance(lead_sponsor, dict):
        lead_sponsor = {}
    sponsor_name = str(lead_sponsor.get("name", "Unknown"))

    # interventions: list of dicts with type, name
    interventions = arms_mod.get("interventions") or []
    if not isinstance(interventions, list):
        interventions = []
    intervention_type: str | None = None
    intervention_name: str | None = None
    if interventions and isinstance(interventions[0], dict):
        it = interventions[0].get("type")
        intervention_type = str(it) if it is not None else None
        iname = interventions[0].get("name")
        intervention_name = str(iname) if iname is not None else None

    # primary outcomes: list of dicts with measure, description
    primary_outcomes = outcomes_mod.get("primaryOutcomes") or []
    if not isinstance(primary_outcomes, list):
        primary_outcomes = []
    primary_outcome_measure: str | None = None
    primary_outcome_description: str | None = None
    if primary_outcomes and isinstance(primary_outcomes[0], dict):
        pm = primary_outcomes[0].get("measure")
        primary_outcome_measure = str(pm) if pm is not None else None
        pd_val = primary_outcomes[0].get("description")
        primary_outcome_description = str(pd_val) if pd_val is not None else None

    # dates
    start_date_struct = status_mod.get("startDateStruct") or {}
    if not isinstance(start_date_struct, dict):
        start_date_struct = {}
    start_date_str = start_date_struct.get("date")
    start_date = parse_date(str(start_date_str) if start_date_str is not None else None)

    completion_date_struct = status_mod.get("completionDateStruct") or {}
    if not isinstance(completion_date_struct, dict):
        completion_date_struct = {}
    completion_date_str = completion_date_struct.get("date")
    completion_date = parse_date(str(completion_date_str) if completion_date_str is not None else None)

    # location country: first location's country
    locations = contacts_mod.get("locations") or []
    if not isinstance(locations, list):
        locations = []
    location_country: str | None = None
    if locations and isinstance(locations[0], dict):
        lc = locations[0].get("country")
        location_country = str(lc) if lc is not None else None

    # enrollment
    enrollment_info = design_mod.get("enrollmentInfo") or {}
    if not isinstance(enrollment_info, dict):
        enrollment_info = {}
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
        intervention_type=intervention_type,
        intervention_name=intervention_name,
        primary_outcome_description=primary_outcome_description,
        primary_outcome_measure=primary_outcome_measure,
        start_date=start_date,
        completion_date=completion_date,
        location_country=location_country,
        enrollment_number=enrollment_number,
        raw_data=study,  # type: ignore[typeddict-item]
    )
