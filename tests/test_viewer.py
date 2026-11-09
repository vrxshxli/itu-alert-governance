"""Viewer data layer, HTTP server and static export (temp dirs; no model calls)."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from agents import approvals
from agents.audit import AuditLog
from viewer import data
from viewer.server import make_server

RID = "run-20261108-120000-abcdef12"
REC = dict(run_id=RID, kb_version="k", model="m", event_id="E1", agent="telecom_operator", inputs_seen=["x"], retrieved_chunks=[],
           reasoning_summary="s", claims=[], flags=[], recommended_action={"action": "report_network_status", "detail": "d"},
           evidence_status="not_established_from_public_sources", human_approval={"required": True, "status": "pending"}, messages_sent=[])


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.setattr(approvals, "RUNS", tmp_path)
    AuditLog(tmp_path / f"{RID}.jsonl").append(REC)
    AuditLog(tmp_path / f"{RID}.baseline.jsonl").append({**REC, "agent": "baseline:telecom_operator", "human_approval": {"required": True, "status": "pending"}})
    (tmp_path / f"{RID}.manifest.json").write_text(json.dumps({"run_id": RID}))
    return tmp_path


def test_list_and_load_run(runs):
    assert data.list_runs(runs) == [RID]
    r = data.load_run(RID, runs)
    assert len(r["grounded"]) == 1 and len(r["baseline"]) == 1 and r["chain"]["grounded"]["ok"] and r["chain"]["baseline"]["ok"]
    assert len(r["scenario"]["events"]) == 6 and "NO_MANDATE_FOUND" in r["flag_meaning"]


@pytest.mark.parametrize("bad", ["../etc/passwd", "run-1", "run-20261108-120000-ABCDEF12", "run-20261108-120000-abcdef12/../x", ""])
def test_run_id_is_strictly_validated(bad, runs):
    with pytest.raises(ValueError):
        data.load_run(bad, runs)
    with pytest.raises(ValueError):
        data.approve(bad, "h", "approved", "me")


def test_tampered_log_shows_broken_chain(runs):
    p = runs / f"{RID}.jsonl"
    p.write_text(p.read_text().replace('"E1"', '"E9"'))
    assert not data.load_run(RID, runs)["chain"]["grounded"]["ok"]


def test_approve_needs_name_pending_record_and_is_final(runs):
    h = data.load_run(RID, runs)["grounded"][0]["hash"]
    with pytest.raises(ValueError):
        data.approve(RID, h, "approved", "  ", runs_dir=runs)
    with pytest.raises(ValueError):
        data.approve(RID, "0" * 64, "approved", "Shivam", runs_dir=runs)
    data.approve(RID, h, "approved", "Shivam", "ok", runs_dir=runs)
    assert data.load_run(RID, runs)["approvals"][h]["by"] == "Shivam"
    with pytest.raises(ValueError):
        data.approve(RID, h, "rejected", "Shivam", runs_dir=runs)


def test_chunk_info_cites_arabic_for_unofficial_translation_and_can_omit_text():
    import chromadb

    col = chromadb.EphemeralClient().get_or_create_collection("viewer_test")
    col.add(ids=["ae-dl-2-2011-ncema-en-unofficial:art5"], documents=["x" * 2000], embeddings=[[1.0, 0.0]],
            metadatas=[{"doc_id": "ae-dl-2-2011-ncema-en-unofficial", "article": "Art. 5", "authority_status": "current_authoritative",
                        "translation_status": "unofficial_translation", "url": "https://u"}])
    full = data.chunk_info("ae-dl-2-2011-ncema-en-unofficial:art5", col)
    assert "Arabic original, authoritative" in full["citation"] and "uaelegislation.gov.ae/ar/" in full["citation"]
    assert len(full["excerpt"]) <= data.EXCERPT + 3
    assert "excerpt" not in data.chunk_info("ae-dl-2-2011-ncema-en-unofficial:art5", col, with_text=False)
    assert data.chunk_info("missing", col) is None


@pytest.fixture
def server(runs):
    srv = make_server(0, runs)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


def get(srv, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}{path}") as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def post(srv, body):
    req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/api/approve", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_server_binds_to_localhost_only_and_serves_page_and_api(server):
    assert server.server_address[0] == "127.0.0.1"
    code, html = get(server, "/")
    assert code == 200 and "Alert Governance Stress-Test" in html and "does not assess UAE institutions" in html
    assert json.loads(get(server, "/api/runs")[1]) == [RID]
    assert json.loads(get(server, f"/api/run/{RID}")[1])["run_id"] == RID
    assert get(server, "/api/run/..%2F..%2Fetc%2Fpasswd")[0] in (400, 404)
    assert get(server, "/nope")[0] == 404


def test_server_approve_endpoint_rejects_anonymous_and_accepts_named_human(server, runs):
    h = data.load_run(RID, runs)["grounded"][0]["hash"]
    assert post(server, {"run_id": RID, "hash": h, "decision": "approved", "by": ""})[0] == 400
    assert post(server, {"run_id": RID, "hash": h, "decision": "maybe", "by": "S"})[0] == 400
    assert post(server, {"run_id": RID, "hash": h})[0] == 400
    code, body = post(server, {"run_id": RID, "hash": h, "decision": "approved", "by": "Shivam"})
    assert code == 200 and json.loads(body)["decision"] == "approved"
    assert post(server, {"run_id": RID, "hash": h, "decision": "rejected", "by": "Shivam"})[0] == 400


def test_static_export_embeds_data_and_cannot_break_out_of_its_script_tag(runs, monkeypatch):
    import scripts.export_viewer as ex

    real_load = data.load_run
    monkeypatch.setattr(data, "list_runs", lambda d=None: [RID])
    monkeypatch.setattr(data, "load_run", lambda rid, d=None: real_load(rid, runs))
    monkeypatch.setattr(data, "report_bundle", lambda d=None: {"gap_report": "# G </script><b>x</b>", "scorecard": "# S", "gap_analysis": None})
    html = ex.build(RID)
    assert "window.__EXPORT__ = " in html and RID in html and "report_network_status" in html
    payload = html.split("window.__EXPORT__ = ")[1].split(";</script>")[0]
    assert "</" not in payload  # a report containing </script> cannot close the tag early
    assert html.count("<script>") == 2
