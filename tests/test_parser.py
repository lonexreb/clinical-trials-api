"""Tests for the CT.gov study parser."""

import datetime

from app.services.parser import parse_date, parse_study


class TestParseDate:
    def test_iso_full_date(self) -> None:
        assert parse_date("2018-11-29") == datetime.date(2018, 11, 29)

    def test_year_month(self) -> None:
        assert parse_date("2015-10") == datetime.date(2015, 10, 1)

    def test_month_year_text(self) -> None:
        assert parse_date("January 2024") == datetime.date(2024, 1, 1)

    def test_month_day_year_text(self) -> None:
        assert parse_date("January 15, 2024") == datetime.date(2024, 1, 15)

    def test_none_input(self) -> None:
        assert parse_date(None) is None

    def test_empty_string(self) -> None:
        assert parse_date("") is None

    def test_whitespace_only(self) -> None:
        assert parse_date("   ") is None

    def test_invalid_string(self) -> None:
        assert parse_date("not a date") is None

    def test_iso_with_whitespace(self) -> None:
        assert parse_date("  2023-06-01  ") == datetime.date(2023, 6, 1)

    def test_various_months(self) -> None:
        assert parse_date("March 2023") == datetime.date(2023, 3, 1)
        assert parse_date("December 2020") == datetime.date(2020, 12, 1)

    def test_full_text_various(self) -> None:
        assert parse_date("March 5, 2023") == datetime.date(2023, 3, 5)
        assert parse_date("December 31, 2020") == datetime.date(2020, 12, 31)


COMPLETE_STUDY: dict[str, object] = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT12345678",
            "briefTitle": "A Study of Drug X in Patients with Cancer",
        },
        "statusModule": {
            "overallStatus": "RECRUITING",
            "startDateStruct": {"date": "2023-01-15", "type": "ACTUAL"},
            "completionDateStruct": {"date": "2025-12-31", "type": "ANTICIPATED"},
        },
        "designModule": {
            "phases": ["PHASE3"],
            "enrollmentInfo": {"count": 500, "type": "ESTIMATED"},
        },
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "Pfizer", "class": "INDUSTRY"},
        },
        "armsInterventionsModule": {
            "interventions": [
                {"type": "DRUG", "name": "Drug X", "description": "Experimental drug"},
                {"type": "DRUG", "name": "Placebo", "description": "Placebo comparator"},
            ],
        },
        "outcomesModule": {
            "primaryOutcomes": [
                {
                    "measure": "Overall Survival",
                    "description": "Time from randomization to death from any cause",
                    "timeFrame": "Up to 5 years",
                },
            ],
        },
        "contactsLocationsModule": {
            "locations": [
                {"facility": "Hospital A", "city": "New York", "country": "United States"},
                {"facility": "Hospital B", "city": "London", "country": "United Kingdom"},
            ],
        },
    },
}


class TestParseStudy:
    def test_complete_study(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["trial_id"] == "NCT12345678"
        assert result["title"] == "A Study of Drug X in Patients with Cancer"
        assert result["phase"] == "PHASE3"
        assert result["status"] == "RECRUITING"
        assert result["sponsor_name"] == "Pfizer"
        assert result["intervention_type"] == "DRUG"
        assert result["intervention_name"] == "Drug X"
        assert result["primary_outcome_measure"] == "Overall Survival"
        assert result["primary_outcome_description"] == "Time from randomization to death from any cause"
        assert result["start_date"] == datetime.date(2023, 1, 15)
        assert result["completion_date"] == datetime.date(2025, 12, 31)
        assert result["location_country"] == "United States"
        assert result["enrollment_number"] == 500

    def test_missing_interventions_module(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["intervention_type"] is None
        assert result["intervention_name"] is None

    def test_missing_outcomes_module(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["primary_outcome_measure"] is None
        assert result["primary_outcome_description"] is None

    def test_missing_locations_module(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["location_country"] is None

    def test_empty_phases_list(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {"phases": []},
            },
        }
        result = parse_study(study)
        assert result["phase"] is None

    def test_missing_enrollment(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["enrollment_number"] is None

    def test_missing_date_structs(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["start_date"] is None
        assert result["completion_date"] is None

    def test_null_modules(self) -> None:
        """Modules set to None instead of being absent."""
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": None,
                "armsInterventionsModule": None,
                "outcomesModule": None,
                "contactsLocationsModule": None,
            },
        }
        result = parse_study(study)
        assert result["phase"] is None
        assert result["intervention_type"] is None
        assert result["primary_outcome_measure"] is None
        assert result["location_country"] is None
        assert result["enrollment_number"] is None

    def test_raw_data_preserved(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["raw_data"] is COMPLETE_STUDY

    def test_empty_study(self) -> None:
        """Study with no protocolSection."""
        result = parse_study({})
        assert result["trial_id"] == "UNKNOWN"
        assert result["title"] == ""
        assert result["status"] == "UNKNOWN"
        assert result["sponsor_name"] == "Unknown"

    def test_empty_interventions_list(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
                "armsInterventionsModule": {"interventions": []},
            },
        }
        result = parse_study(study)
        assert result["intervention_type"] is None
        assert result["intervention_name"] is None

    def test_empty_primary_outcomes_list(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
                "outcomesModule": {"primaryOutcomes": []},
            },
        }
        result = parse_study(study)
        assert result["primary_outcome_measure"] is None
        assert result["primary_outcome_description"] is None

    def test_year_month_date_format(self) -> None:
        """CT.gov sometimes returns dates as YYYY-MM."""
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {
                    "overallStatus": "COMPLETED",
                    "startDateStruct": {"date": "2015-10"},
                    "completionDateStruct": {"date": "January 2024"},
                },
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["start_date"] == datetime.date(2015, 10, 1)
        assert result["completion_date"] == datetime.date(2024, 1, 1)
