def test_list_jobs_empty(client):
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    assert response.json() == []

def test_list_candidates_empty(client):
    response = client.get("/api/v1/candidates")
    assert response.status_code == 200
    assert response.json() == []

def test_get_nonexistent_job(client):
    from uuid import uuid4
    response = client.get(f"/api/v1/jobs/{uuid4()}")
    assert response.status_code == 404

def test_get_nonexistent_candidate(client):
    from uuid import uuid4
    response = client.get(f"/api/v1/candidates/{uuid4()}")
    assert response.status_code == 404
