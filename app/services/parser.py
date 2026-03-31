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
    study_type: str | None
    interventions: list[dict[str, object]] | None
    primary_outcomes: list[dict[str, object]] | None
    secondary_outcomes: list[dict[str, object]] | None
    conditions: list[str] | None
    eligibility_criteria: str | None
    mesh_terms: list[str] | None
    references: list[dict[str, object]] | None
    investigators: list[dict[str, object]] | None
    start_date: datetime.date | None
    completion_date: datetime.date | None
    locations: list[dict[str, object]] | None
    enrollment_number: int | None
    source: str
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
    derived = _ensure_dict(study.get("derivedSection", {}))

    id_mod = _ensure_dict(protocol.get("identificationModule", {}))
    status_mod = _ensure_dict(protocol.get("statusModule", {}))
    design_mod = _ensure_dict(protocol.get("designModule", {}))
    sponsor_mod = _ensure_dict(protocol.get("sponsorCollaboratorsModule", {}))
    arms_mod = _ensure_dict(protocol.get("armsInterventionsModule", {}))
    outcomes_mod = _ensure_dict(protocol.get("outcomesModule", {}))
    contacts_mod = _ensure_dict(protocol.get("contactsLocationsModule", {}))
    conditions_mod = _ensure_dict(protocol.get("conditionsModule", {}))
    eligibility_mod = _ensure_dict(protocol.get("eligibilityModule", {}))
    references_mod = _ensure_dict(protocol.get("referencesModule", {}))

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

    # study type: e.g. "INTERVENTIONAL", "OBSERVATIONAL"
    raw_study_type = design_mod.get("studyType")
    study_type = str(raw_study_type) if raw_study_type else None

    # interventions: store full array of dicts
    interventions = _parse_list_of_dicts(arms_mod.get("interventions"))

    # primary outcomes: store full array of dicts
    primary_outcomes = _parse_list_of_dicts(outcomes_mod.get("primaryOutcomes"))

    # secondary outcomes: store full array of dicts
    secondary_outcomes = _parse_list_of_dicts(outcomes_mod.get("secondaryOutcomes"))

    # conditions: list of strings from conditionsModule
    raw_conditions = conditions_mod.get("conditions")
    conditions: list[str] | None = None
    if isinstance(raw_conditions, list) and len(raw_conditions) > 0:
        conditions = [str(c) for c in raw_conditions if c]
        if not conditions:
            conditions = None

    # eligibility criteria: free text from eligibilityModule
    raw_eligibility = eligibility_mod.get("eligibilityCriteria")
    eligibility_criteria = str(raw_eligibility).strip() if raw_eligibility else None
    if eligibility_criteria == "":
        eligibility_criteria = None

    # MeSH terms: from derivedSection.conditionBrowseModule.meshes
    condition_browse = _ensure_dict(derived.get("conditionBrowseModule", {}))
    raw_meshes = condition_browse.get("meshes")
    mesh_terms: list[str] | None = None
    if isinstance(raw_meshes, list) and len(raw_meshes) > 0:
        mesh_terms = [str(m.get("term", "")) for m in raw_meshes if isinstance(m, dict) and m.get("term")]
        if not mesh_terms:
            mesh_terms = None

    # references/DOIs: from referencesModule.references
    references = _parse_list_of_dicts(references_mod.get("references"))

    # investigators: from contactsLocationsModule.overallOfficials
    investigators = _parse_list_of_dicts(contacts_mod.get("overallOfficials"))

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
        study_type=study_type,
        interventions=interventions,
        primary_outcomes=primary_outcomes,
        secondary_outcomes=secondary_outcomes,
        conditions=conditions,
        eligibility_criteria=eligibility_criteria,
        mesh_terms=mesh_terms,
        references=references,
        investigators=investigators,
        start_date=start_date,
        completion_date=completion_date,
        locations=locations,
        enrollment_number=enrollment_number,
        source="clinicaltrials.gov",
        raw_data=study,  # type: ignore[typeddict-item]
    )
