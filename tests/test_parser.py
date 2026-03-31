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
            "studyType": "INTERVENTIONAL",
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
            "secondaryOutcomes": [
                {
                    "measure": "Progression Free Survival",
                    "description": "Time to disease progression or death",
                    "timeFrame": "Up to 3 years",
                },
                {
                    "measure": "Quality of Life",
                    "description": "EORTC QLQ-C30 score change from baseline",
                    "timeFrame": "Every 12 weeks",
                },
            ],
        },
        "conditionsModule": {
            "conditions": ["Lung Cancer", "Non-Small Cell Lung Cancer"],
        },
        "eligibilityModule": {
            "eligibilityCriteria": "Inclusion Criteria:\n- Age >= 18\n- Confirmed NSCLC\n\nExclusion Criteria:\n- Prior chemotherapy",
        },
        "referencesModule": {
            "references": [
                {"pmid": "12345678", "type": "RESULT", "citation": "Smith et al. J Oncol. 2023"},
                {"pmid": "23456789", "type": "BACKGROUND", "citation": "Jones et al. Lancet. 2022"},
            ],
        },
        "contactsLocationsModule": {
            "locations": [
                {"facility": "Hospital A", "city": "New York", "country": "United States"},
                {"facility": "Hospital B", "city": "London", "country": "United Kingdom"},
            ],
            "overallOfficials": [
                {"name": "Dr. Jane Smith", "role": "PRINCIPAL_INVESTIGATOR", "affiliation": "Hospital A"},
            ],
        },
    },
    "derivedSection": {
        "conditionBrowseModule": {
            "meshes": [
                {"id": "D008175", "term": "Lung Neoplasms"},
                {"id": "D002289", "term": "Carcinoma, Non-Small-Cell Lung"},
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
        assert result["start_date"] == datetime.date(2023, 1, 15)
        assert result["completion_date"] == datetime.date(2025, 12, 31)
        assert result["enrollment_number"] == 500

    def test_interventions_full_array(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["interventions"] is not None
        assert len(result["interventions"]) == 2
        assert result["interventions"][0]["type"] == "DRUG"
        assert result["interventions"][0]["name"] == "Drug X"
        assert result["interventions"][1]["name"] == "Placebo"

    def test_primary_outcomes_full_array(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["primary_outcomes"] is not None
        assert len(result["primary_outcomes"]) == 1
        assert result["primary_outcomes"][0]["measure"] == "Overall Survival"

    def test_secondary_outcomes_full_array(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["secondary_outcomes"] is not None
        assert len(result["secondary_outcomes"]) == 2
        assert result["secondary_outcomes"][0]["measure"] == "Progression Free Survival"
        assert result["secondary_outcomes"][1]["measure"] == "Quality of Life"

    def test_locations_full_array(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["locations"] is not None
        assert len(result["locations"]) == 2
        assert result["locations"][0]["country"] == "United States"
        assert result["locations"][1]["city"] == "London"

    def test_conditions_extracted(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["conditions"] is not None
        assert len(result["conditions"]) == 2
        assert result["conditions"][0] == "Lung Cancer"
        assert result["conditions"][1] == "Non-Small Cell Lung Cancer"

    def test_missing_conditions_module(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["conditions"] is None

    def test_empty_conditions_list(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
                "conditionsModule": {"conditions": []},
            },
        }
        result = parse_study(study)
        assert result["conditions"] is None

    def test_null_conditions_module(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
                "conditionsModule": None,
            },
        }
        result = parse_study(study)
        assert result["conditions"] is None

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
        assert result["interventions"] is None

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
        assert result["primary_outcomes"] is None
        assert result["secondary_outcomes"] is None

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
        assert result["locations"] is None

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
        assert result["interventions"] is None
        assert result["primary_outcomes"] is None
        assert result["secondary_outcomes"] is None
        assert result["locations"] is None
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
        assert result["interventions"] is None

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
        assert result["primary_outcomes"] is None

    def test_empty_secondary_outcomes_list(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
                "outcomesModule": {"secondaryOutcomes": []},
            },
        }
        result = parse_study(study)
        assert result["secondary_outcomes"] is None

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

    def test_study_type_extracted(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["study_type"] == "INTERVENTIONAL"

    def test_study_type_missing(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["study_type"] is None

    def test_eligibility_criteria_extracted(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["eligibility_criteria"] is not None
        assert "Age >= 18" in result["eligibility_criteria"]
        assert "Prior chemotherapy" in result["eligibility_criteria"]

    def test_eligibility_criteria_missing(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["eligibility_criteria"] is None

    def test_eligibility_criteria_empty(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
                "eligibilityModule": {"eligibilityCriteria": ""},
            },
        }
        result = parse_study(study)
        assert result["eligibility_criteria"] is None

    def test_mesh_terms_extracted(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["mesh_terms"] is not None
        assert len(result["mesh_terms"]) == 2
        assert "Lung Neoplasms" in result["mesh_terms"]
        assert "Carcinoma, Non-Small-Cell Lung" in result["mesh_terms"]

    def test_mesh_terms_missing_derived_section(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["mesh_terms"] is None

    def test_mesh_terms_empty_meshes(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
            "derivedSection": {
                "conditionBrowseModule": {"meshes": []},
            },
        }
        result = parse_study(study)
        assert result["mesh_terms"] is None

    def test_references_extracted(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["references"] is not None
        assert len(result["references"]) == 2
        assert result["references"][0]["pmid"] == "12345678"

    def test_references_missing(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["references"] is None

    def test_investigators_extracted(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["investigators"] is not None
        assert len(result["investigators"]) == 1
        assert result["investigators"][0]["name"] == "Dr. Jane Smith"
        assert result["investigators"][0]["role"] == "PRINCIPAL_INVESTIGATOR"

    def test_investigators_missing(self) -> None:
        study: dict[str, object] = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
                "designModule": {},
            },
        }
        result = parse_study(study)
        assert result["investigators"] is None

    def test_source_always_set(self) -> None:
        result = parse_study(COMPLETE_STUDY)
        assert result["source"] == "clinicaltrials.gov"

    def test_source_set_for_empty_study(self) -> None:
        result = parse_study({})
        assert result["source"] == "clinicaltrials.gov"
