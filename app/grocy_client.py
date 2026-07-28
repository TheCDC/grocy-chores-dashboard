"""Thin wrapper around grocy-py.

Isolates the exact grocy-py calls this app relies on (confirmed against
grocy-py's docs — see requirements doc §5/§7) so the rest of the app talks
to a small, app-specific interface instead of grocy-py's full surface.
Also the natural place to add retry/error-handling policy later.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from grocy import Grocy
from grocy.data_models.chore import Chore
from grocy.data_models.generic import EntityType
from grocy.errors import GrocyError
from urllib3.exceptions import InsecureRequestWarning

from app.config import Config

# The user deliberately sets GROCY_VERIFY_SSL=false in their environment.
# Every fresh HTTPS connection would otherwise log an InsecureRequestWarning
# — suppress it once at the application level rather than at every request.
warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def _patch_pooling(api_client) -> None:
    """Add connection pooling to a GrocyApiClient instance.

    grocy-py v0.1.0's ``GrocyApiClient`` calls module-level
    ``requests.get/post/put/delete`` on every request — no
    ``requests.Session``, so each call creates a brand-new TCP+TLS
    connection.  For a remote Grocy behind a dynamic-DNS hostname this
    adds ~3-4 s of handshake latency per request and floods logs with
    ``InsecureRequestWarning`` when ``verify_ssl=False``.

    This patch attaches a persistent Session and replaces the 4 HTTP
    methods on *the instance* to use it, preserving the original
    logging/error-handling behavior exactly.
    """
    session = requests.Session()
    session.verify = api_client._verify_ssl
    session.headers.update(api_client._headers)

    def _request(method: str, end_url: str, **kwargs):
        req_url = urljoin(api_client._base_url, end_url)
        resp = session.request(method, req_url, **kwargs)
        if resp.status_code >= 400:
            raise GrocyError(resp)
        if len(resp.content) > 0:
            return resp.json()
        return None

    def _get(end_url, query_filters=None):
        params = None
        if query_filters:
            params = {"query[]": query_filters}
        return _request("GET", end_url, params=params)

    def _post(end_url, data=None):
        return _request("POST", end_url, json=data)

    def _put(end_url, data=None):
        headers = api_client._headers.copy()
        headers["accept"] = "*/*"
        if isinstance(data, dict):
            headers["Content-Type"] = "application/json"
            data = json.dumps(data)
        else:
            headers["Content-Type"] = "application/octet-stream"
        return _request("PUT", end_url, data=data, headers=headers)

    def _delete(end_url):
        return _request("DELETE", end_url)

    api_client._do_get_request = _get
    api_client._do_post_request = _post
    api_client._do_put_request = _put
    api_client._do_delete_request = _delete


@dataclass
class GrocyClient:
    """Wraps a `grocy.Grocy` instance with just what this app needs."""

    _client: Grocy

    @classmethod
    def from_config(cls, config: Config) -> "GrocyClient":
        client = Grocy(
            config.grocy_base_url,
            config.grocy_api_key,
            port=config.grocy_port,
            path=config.grocy_path,
            verify_ssl=config.grocy_verify_ssl,
        )
        _patch_pooling(client._api_client)
        return cls(_client=client)

    # --- Reads -------------------------------------------------------

    def list_chores(self):
        """Return all chores with the fields this app needs — via 2 bulk
        API requests total, regardless of how many chores exist.

        `grocy-py`'s `chores.list(get_details=True)` (what this method
        used to call) costs 2 *extra* requests per chore on top of the
        initial list — confirmed by reading grocy-py's source:
        `Chore.get_details()` calls `api_client.get_chore(id)` (chore
        detail) *and* `api_client.get_userfields("chores", id)`,
        separately, for every chore. That's the "dozens to hundreds of
        requests" behavior — O(2N+1) requests for N chores, and it fires
        on every poll (REFRESH_INTERVAL_SECONDS) plus after every action.

        This app doesn't use userfields at all, and the per-chore detail
        call is redundant with a bulk endpoint that already exists:

        - `chores.list(get_details=False)`: 1 request, gives each
          chore's *computed status* (`next_estimated_execution_time`,
          `last_tracked_time`) — this is what we actually need the
          per-chore detail call for, and it's already available in bulk.
        - `generic.list(EntityType.CHORES)`: 1 request, gives *every*
          chore's master data (`name`, `description`, `assignment_type`,
          `next_execution_assigned_to_user_id`) in one shot — confirmed
          against grocy-py's source that this returns the same field
          shape as the "chore" sub-object in the per-chore detail
          response (`ChoreData` model), just for all chores at once.

        Merging these two client-side gives everything
        `services/chore_service.py`'s `_to_dashboard_chore()` needs,
        reconstructed as real `Chore` objects (pydantic coerces the raw
        `assignment_type` string into the `AssignmentType` enum
        automatically) — so nothing downstream of this method has to
        change. Total: 2 requests instead of 2N+1.
        """
        status_by_id = {
            c.id: c for c in self._client.chores.list(get_details=False)
        }
        master_rows = self._client.generic.list(EntityType.CHORES)

        merged: list[Chore] = []
        for row in master_rows:
            status = status_by_id.get(row["id"])
            merged.append(
                Chore(
                    id=row["id"],
                    name=row.get("name"),
                    description=row.get("description"),
                    assignment_type=row.get("assignment_type"),
                    next_execution_assigned_to_user_id=row.get(
                        "next_execution_assigned_to_user_id"
                    ),
                    next_estimated_execution_time=(
                        status.next_estimated_execution_time if status else None
                    ),
                    last_tracked_time=status.last_tracked_time if status else None,
                )
            )
        return merged

    def list_users(self):
        """Return all Grocy users (unfiltered — include-list filtering
        happens in services/chore_service.py, not here)."""
        return self._client.users.list()

    # --- Writes --------------------------------------------------------

    def mark_done(self, chore_id: int, done_by_user_id: int):
        """Mark a chore as done by the given user.

        Maps to grocy.chores.execute(chore_id, done_by=..., skipped=False).

        Returns grocy-py's execute() result unmodified: a plain dict
        parsed from Grocy's POST /chores/{id}/execute response (a chore
        log entry, including "id") — confirmed by reading grocy-py's
        source (GrocyApiClient._do_post_request returns resp.json()).
        Passed through so ChoreService can extract that "id" to power the
        "Undo" notification action.
        """
        return self._client.chores.execute(
            chore_id=chore_id, done_by=done_by_user_id, skipped=False
        )

    def skip(self, chore_id: int, done_by_user_id: int):
        """Skip a chore's current due date, advancing to the next occurrence.

        Same underlying call as mark_done, with skipped=True — grocy-py
        does not have a separate skip method (confirmed via grocy-py
        source). Return value: same as mark_done() — a dict with "id".
        """
        return self._client.chores.execute(
            chore_id=chore_id, done_by=done_by_user_id, skipped=True
        )

    def reassign(self, chore_id: int, new_user_id: int) -> None:
        """Change a chore's next-execution assignee.

        No dedicated reassignment method exists on grocy-py's
        ChoreManager; this goes through the generic entity-update API
        against the `next_execution_assigned_to_user_id` field.

        Callers must guard this: reassignment is only offered for chores
        with `assignment_type == AssignmentType.NO_ASSIGNMENT` (enforced
        in ChoreService.reassign() and disabled in the UI for other
        chores — see DashboardChore.is_manually_reassignable). For
        WHO_LEAST_DID_FIRST / RANDOM / IN_ALPHABETICAL_ORDER chores,
        Grocy's own assignment logic may overwrite a manual change on the
        next execution or calculate_next_assignments() call, so this
        method does not attempt to support them.
        """
        self._client.generic.update(
            EntityType.CHORES,
            object_id=chore_id,
            data={"next_execution_assigned_to_user_id": new_user_id},
        )

    def undo(self, execution_id: int) -> None:
        """Undo a chore execution (mark-done or skip).

        Exposed in the UI as an "Undo" action on the notification shown
        right after mark-done/skip — see ui/dashboard.py's
        _handle_mark_done/_handle_skip. Requires the execution_id
        returned by the preceding execute() call; see mark_done()'s
        docstring for the open question about that return shape.
        """
        self._client.chores.undo(execution_id=execution_id)
