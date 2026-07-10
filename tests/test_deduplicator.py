import itertools

import pytest

from research_engine.deduplicator import Deduplicator
from research_engine.publication_identity import PublicationIdentityResolver


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


@pytest.mark.parametrize(
    "doi",
    [
        "doi:10.1000/Example",
        "https://doi.org/10.1000/Example",
        "http://doi.org/10.1000/Example",
        "https://dx.doi.org/10.1000/Example",
        "http://dx.doi.org/10.1000/Example",
        "  HTTPS://DOI.ORG/10.1000/EXAMPLE  ",
    ],
)
def test_doi_variants_normalize_to_primary_identity(doi):
    record = {"doi": doi}

    assert Deduplicator().cluster([record]) == {
        "doi:10.1000/example": [record]
    }


@pytest.mark.parametrize("doi", [None, "", "   ", "doi:   "])
def test_blank_doi_falls_back_to_title(doi):
    record = {"doi": doi, "title": "Usable title"}

    assert Deduplicator().cluster([record]) == {
        "title:usable title": [record]
    }


def test_title_normalization_handles_unicode_whitespace_and_punctuation():
    records = [
        {"provider": "a", "title": "  “Cafe\u0301\u00a0\u00a0Studies…”  "},
        {"provider": "b", "title": '"Café Studies..."'},
    ]

    assert Deduplicator().cluster(records) == {
        "title:café studies": records
    }


def test_typographic_internal_punctuation_is_normalized():
    resolver = PublicationIdentityResolver()

    assert resolver.normalize_title("Rock—solid ‘result’") == "rock-solid 'result"
    assert resolver.normalize_title("Rock-solid 'result'") == "rock-solid 'result"


@pytest.mark.parametrize(
    ("scientific", "plain"),
    [
        ("H₂O", "H2O"),
        ("CO₂", "CO2"),
        ("x²", "x2"),
        ("ℝ", "R"),
        ("α", "a"),
        ("β-phase", "b-phase"),
    ],
)
def test_scientifically_distinct_titles_remain_separate(scientific, plain):
    records = [{"title": scientific}, {"title": plain}]

    clusters = Deduplicator().cluster(records)

    assert len(clusters) == 2
    assert sum(map(len, clusters.values())) == 2


@pytest.mark.parametrize(
    ("variant", "ascii_title"),
    [
        ("“Quoted ‘result’”", '"Quoted \'result\'"'),
        ("phase–transition", "phase-transition"),
        ("phase—transition", "phase-transition"),
        ("phase−transition", "phase-transition"),
        ("Repeated\u00a0  whitespace", "Repeated whitespace"),
        ("...Decorative title!!!", "Decorative title"),
    ],
)
def test_non_scientific_title_variants_normalize_equivalently(
    variant, ascii_title
):
    resolver = PublicationIdentityResolver()

    assert resolver.normalize_title(variant) == resolver.normalize_title(
        ascii_title
    )


def test_internal_punctuation_and_mathematical_operators_are_preserved():
    resolver = PublicationIdentityResolver()

    assert resolver.normalize_title("Na⁺/K⁺: x − y ≠ 0") == (
        "na⁺/k⁺: x − y ≠ 0"
    )


def test_doi_less_record_bridges_to_unambiguous_doi_by_title():
    records = [
        {"provider": "crossref", "doi": "10.1000/shared", "title": "Shared"},
        {"provider": "openalex", "title": " shared "},
    ]

    assert Deduplicator().cluster(records) == {
        "doi:10.1000/shared": records
    }


def test_same_title_does_not_merge_distinct_dois():
    records = [
        {"provider": "a", "doi": "10.1000/a", "title": "Shared"},
        {"provider": "b", "doi": "10.1000/b", "title": "Shared"},
    ]

    assert Deduplicator().cluster(records) == {
        "doi:10.1000/a": [records[0]],
        "doi:10.1000/b": [records[1]],
    }


def test_doi_less_record_with_ambiguous_title_remains_unresolved():
    records = [
        {"provider": "a", "doi": "10.1000/a", "title": "Shared"},
        {"provider": "b", "doi": "10.1000/b", "title": "Shared"},
        {"provider": "c", "title": "Shared"},
    ]

    assert Deduplicator().cluster(records) == {
        "doi:10.1000/a": [records[0]],
        "doi:10.1000/b": [records[1]],
        "title:shared": [records[2]],
    }


def test_records_without_doi_or_title_never_collapse():
    records = [
        {"provider": "a", "abstract": "First"},
        {"provider": "b", "abstract": "Second"},
    ]

    clusters = Deduplicator().cluster(records)

    assert len(clusters) == 2
    assert all(key.startswith("record:") for key in clusters)
    clustered = [record for cluster in clusters.values() for record in cluster]
    assert {id(record) for record in clustered} == {id(record) for record in records}


def test_clustering_is_independent_of_input_permutation_and_loses_no_records():
    records = [
        {"provider": "z", "title": "Title only"},
        {"provider": "b", "doi": "doi:10.1000/shared", "title": "Shared"},
        {"provider": "a", "title": "Shared"},
        {"provider": "y", "abstract": "No identity"},
    ]
    expected = Deduplicator().cluster(records)

    for permutation in itertools.permutations(records):
        actual = Deduplicator().cluster(permutation)
        assert actual == expected
        assert sum(map(len, actual.values())) == len(records)
