from research_engine.deduplicator import Deduplicator


def test_cluster_one_provider():
    record = {"provider": "crossref", "doi": "10.1000/one"}

    assert Deduplicator().cluster([record]) == {
        "doi:10.1000/one": [record],
    }


def test_cluster_two_providers_with_same_doi_keeps_both_records():
    records = [
        {"provider": "crossref", "doi": "10.1000/shared"},
        {"provider": "openalex", "doi": "10.1000/shared"},
    ]

    assert Deduplicator().cluster(records) == {
        "doi:10.1000/shared": records,
    }


def test_cluster_three_providers_with_same_doi_keeps_every_record():
    records = [
        {"provider": "crossref", "doi": "10.1000/shared"},
        {"provider": "openalex", "doi": "10.1000/shared"},
        {"provider": "scopus", "doi": "10.1000/shared"},
    ]

    assert Deduplicator().cluster(records) == {
        "doi:10.1000/shared": records,
    }


def test_cluster_uses_title_when_doi_is_missing():
    records = [
        {"provider": "crossref", "title": "Shared Publication"},
        {"provider": "openalex", "title": " shared publication "},
    ]

    assert Deduplicator().cluster(records) == {
        "title:shared publication": records,
    }


def test_cluster_keeps_different_publications_separate():
    first = {"provider": "crossref", "doi": "10.1000/one"}
    second = {"provider": "openalex", "doi": "10.1000/two"}

    assert Deduplicator().cluster([first, second]) == {
        "doi:10.1000/one": [first],
        "doi:10.1000/two": [second],
    }
