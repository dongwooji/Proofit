"""HTTP-level tests: routing, status codes, Korean error bodies, and commits."""

from fastapi.testclient import TestClient


def _create_job(client: TestClient, **overrides) -> dict:
    body = {
        "company_name": "예시랩스",
        "title": "AI Engineer 인턴 (채용연계형)",
        "employment_type": "CONVERSION_INTERN",
        "experience_level": "NEW_GRAD",
        "deadline_type": "DATE",
        "deadline_date": "2026-12-15",
        "source": {"platform": "rocketpunch", "external_id": "rp-1", "source_url": "https://x"},
    }
    body.update(overrides)
    res = client.post("/api/jobs", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_job_create_get_update_list(client: TestClient) -> None:
    job = _create_job(client)
    assert job["sources"][0]["external_id"] == "rp-1"
    assert job["detail_status"] == "LISTING_ONLY"

    res = client.patch(f"/api/jobs/{job['id']}", json={"status": "OPEN"})
    assert res.status_code == 200
    assert res.json()["status"] == "OPEN"

    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "OPEN"
    listed = client.get("/api/jobs", params={"q": "채용연계형", "status": "OPEN"}).json()
    assert [j["id"] for j in listed] == [job["id"]]
    assert client.get("/api/jobs", params={"status": "CLOSED"}).json() == []


def test_job_errors_are_korean_with_codes(client: TestClient) -> None:
    res = client.get("/api/jobs/999")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"
    assert "찾을 수 없습니다" in res.json()["error"]["message"]

    _create_job(client)
    dup = client.post(
        "/api/jobs",
        json={
            "company_name": "a",
            "title": "b",
            "source": {"platform": "rocketpunch", "external_id": "rp-1"},
        },
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "conflict"

    bad = client.post(
        "/api/jobs", json={"company_name": "a", "title": "b", "deadline_type": "DATE"}
    )
    assert bad.status_code == 422
    assert "마감일" in bad.json()["error"]["message"]


def test_failed_write_is_not_committed(client: TestClient) -> None:
    client.post("/api/jobs", json={"company_name": "a", "title": "b", "deadline_type": "DATE"})
    assert client.get("/api/jobs").json() == []


def test_sources_and_snapshots(client: TestClient) -> None:
    job = _create_job(client)
    res = client.post(f"/api/jobs/{job['id']}/sources", json={"platform": "manual"})
    assert res.status_code == 201
    assert len(client.get(f"/api/jobs/{job['id']}/sources").json()) == 2

    first = client.post(f"/api/jobs/{job['id']}/snapshots", json={"content": "자격요건 ..."})
    assert first.status_code == 201
    again = client.post(f"/api/jobs/{job['id']}/snapshots", json={"content": "자격요건 ..."})
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert len(client.get(f"/api/jobs/{job['id']}/snapshots").json()) == 1


def test_application_status_flow(client: TestClient) -> None:
    job = _create_job(client)
    app = client.post("/api/applications", json={"job_id": job["id"]}).json()
    assert app["status"] == "REVIEWING"

    for target in ("PLANNED", "APPLIED", "INTERVIEW"):
        res = client.patch(f"/api/applications/{app['id']}/status", json={"to_status": target})
        assert res.status_code == 200, res.text
    assert client.get(f"/api/applications/{app['id']}").json()["applied_at"] is not None

    bad = client.patch(f"/api/applications/{app['id']}/status", json={"to_status": "SKIPPED"})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "invalid_transition"

    events = client.get(f"/api/applications/{app['id']}/events").json()
    assert [e["to_status"] for e in events] == ["REVIEWING", "PLANNED", "APPLIED", "INTERVIEW"]
    assert [
        a["id"] for a in client.get("/api/applications", params={"status": "INTERVIEW"}).json()
    ] == [app["id"]]

    res = client.patch(f"/api/applications/{app['id']}", json={"note": "2차 면접 준비"})
    assert res.json()["note"] == "2차 면접 준비"


def test_profile_projects_and_evidence_versions(client: TestClient) -> None:
    profile = client.put("/api/profile", json={"display_name": "홍길동"}).json()
    assert client.get("/api/profile").json()["id"] == profile["id"]

    project = client.post(
        "/api/projects", json={"title": "Agentic RAG", "my_role": "검색 담당"}
    ).json()
    assert (
        client.patch(f"/api/projects/{project['id']}", json={"team_size": 3}).json()["team_size"]
        == 3
    )

    item = client.post(
        "/api/evidence",
        json={
            "kind": "PROJECT",
            "project_id": project["id"],
            "claim": "하이브리드 검색 파이프라인 구현",
            "skills": ["Python"],
        },
    ).json()
    assert item["current_version"]["version_no"] == 1
    assert item["current_version"]["review_status"] == "DRAFT"

    v2 = client.patch(f"/api/evidence/{item['id']}", json={"metric": "Recall@10 0.62 → 0.81"})
    assert v2.status_code == 201
    assert v2.json()["version_no"] == 2

    confirmed = client.post(f"/api/evidence-versions/{v2.json()['id']}/confirm")
    assert confirmed.json()["review_status"] == "CONFIRMED"
    assert client.post(f"/api/evidence-versions/{v2.json()['id']}/confirm").status_code == 409

    versions = client.get(f"/api/evidence/{item['id']}/versions").json()
    assert [(v["version_no"], v["metric"]) for v in versions] == [
        (1, None),
        (2, "Recall@10 0.62 → 0.81"),
    ]
    listed = client.get("/api/evidence", params={"project_id": project["id"]}).json()
    assert listed[0]["current_version"]["version_no"] == 2
