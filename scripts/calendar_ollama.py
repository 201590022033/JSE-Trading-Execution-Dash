"""Idle-only, local sourced calendar expectation drafts; never trading or training.

The owner's shared Ollama11434 is untouched. One owned11435 server is contained
in a Windows kill-on-close job. A persisted reservation consumes the event/day
budget even after crashes or failures. No automatic retry spends another call.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HOST = "http://127.0.0.1:11435"
MODEL = "llama3:latest"
MODEL_DIGEST = "365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1"
ACCOUNT = "calendar-ollama-runner-v1"
VERSION = "calendar-ollama-runner-v1"
IDLE_SECONDS = 600
TIMEOUT_SECONDS = 180
MAX_BYTES = 100_000
GIB = 1024 ** 3
MIN_START_MEMORY = 7 * GIB
MIN_RUNNING_MEMORY = 3 * GIB // 2
SAST = ZoneInfo("Africa/Johannesburg")


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def utcnow():
    return datetime.now(timezone.utc)


def windows_idle_seconds():
    """Actual last keyboard/mouse input; unsupported platforms fail closed."""
    if os.name != "nt":
        raise RuntimeError("Windows idle telemetry required")
    import ctypes
    from ctypes import wintypes
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        raise RuntimeError("Idle telemetry unavailable")
    elapsed = (ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xffffffff
    return elapsed / 1000.0


def below_normal():
    if os.name != "nt":
        raise RuntimeError("Windows priority controls required")
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000):
        raise RuntimeError("Below-normal process priority required")


def available_memory_bytes():
    if os.name != "nt":
        raise RuntimeError("Windows memory telemetry required")
    import ctypes
    from ctypes import wintypes
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
            (name, ctypes.c_uint64) for name in ("total_phys", "available_phys", "total_page",
                "available_page", "total_virtual", "available_virtual", "available_extended")]
    status = MEMORYSTATUSEX(); status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError("Memory telemetry unavailable")
    return status.available_phys


class OwnedOllama:
    """Owned process tree, atomically placed in kill-on-close job before execution.

    Closing its sole noninherited job handle kills the server and model runner,
    including when Task Scheduler stops this parent. Existing11434 is untouched.
    """
    def __init__(self, executable, folder, *, command=None):
        self.executable, self.folder = Path(executable), Path(folder)
        self.command = command or [str(self.executable), "serve"]
        self.kernel = self.job = self.process = None
        self.pid = None

    def __enter__(self):
        if os.name != "nt" or not self.executable.is_file():
            raise RuntimeError("Existing official Windows Ollama executable required")
        # Never take over or send generation to a pre-existing listener.
        probe = socket.socket()
        try:
            probe.bind(("127.0.0.1", 11435))
        finally:
            probe.close()
        import ctypes
        from ctypes import wintypes as w
        class BASIC(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", w.DWORD), ("min_working", ctypes.c_size_t), ("max_working", ctypes.c_size_t),
                ("active", w.DWORD), ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("r", "w", "o", "rb", "wb", "ob")]
        class EXTENDED(ctypes.Structure):
            _fields_ = [("basic", BASIC), ("io", IO), ("process_limit", ctypes.c_size_t),
                ("job_limit", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]
        class STARTUP(ctypes.Structure):
            _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR), ("title", w.LPWSTR),
                ("x", w.DWORD), ("y", w.DWORD), ("sx", w.DWORD), ("sy", w.DWORD), ("cx", w.DWORD),
                ("cy", w.DWORD), ("fill", w.DWORD), ("flags", w.DWORD), ("show", w.WORD),
                ("reserved2_size", w.WORD), ("reserved2", ctypes.POINTER(ctypes.c_byte)),
                ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]
        class PROCESS(ctypes.Structure):
            _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.argtypes = (ctypes.c_void_p, w.LPCWSTR); k.CreateJobObjectW.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = (w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD)
        k.AssignProcessToJobObject.argtypes = (w.HANDLE, w.HANDLE)
        k.CloseHandle.argtypes = (w.HANDLE,)
        k.TerminateProcess.argtypes = (w.HANDLE, w.UINT)
        k.WaitForSingleObject.argtypes = (w.HANDLE, w.DWORD)
        k.ResumeThread.argtypes = (w.HANDLE,); k.ResumeThread.restype = w.DWORD
        k.CreateProcessW.argtypes = (w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL,
            w.DWORD, ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(STARTUP), ctypes.POINTER(PROCESS))
        self.kernel = k
        self.job = k.CreateJobObjectW(None, None)
        limits = EXTENDED()
        # Kill descendants on handle close; enforce below-normal priority on all
        # job processes, even a backend that explicitly requests normal priority.
        limits.basic.flags = 0x2000 | 0x20
        limits.basic.priority = 0x4000
        if not self.job or not k.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.__exit__(None, None, None)
            raise RuntimeError("Owned kill-on-close job required")
        # Minimal process environment: no database/provider secrets or model paths.
        safe_names = {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP", "COMSPEC",
            "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "PROGRAMFILES",
            "PROGRAMFILES(X86)", "PROGRAMW6432", "PROCESSOR_ARCHITECTURE"}
        env = {name: value for name, value in os.environ.items() if name.upper() in safe_names}
        env.update(OLLAMA_HOST="127.0.0.1:11435", OLLAMA_NO_CLOUD="1", OLLAMA_NOPRUNE="1",
            OLLAMA_NUM_PARALLEL="1", OLLAMA_MAX_LOADED_MODELS="1", OLLAMA_MAX_QUEUE="1",
            OLLAMA_KEEP_ALIVE="0", OLLAMA_LOAD_TIMEOUT="120s", CUDA_VISIBLE_DEVICES="-1",
            HIP_VISIBLE_DEVICES="-1", GGML_VK_VISIBLE_DEVICES="-1")
        block = ctypes.create_unicode_buffer("\0".join(f"{key}={value}"
            for key, value in sorted(env.items(), key=lambda item: item[0].upper())) + "\0\0")
        startup = STARTUP(); startup.cb = ctypes.sizeof(startup)
        proc = PROCESS()
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(self.command))
        # CREATE_SUSPENDED|CREATE_NO_WINDOW|CREATE_UNICODE_ENVIRONMENT|BELOW_NORMAL_PRIORITY_CLASS
        if not k.CreateProcessW(str(self.executable), command, None, None, False,
                0x4 | 0x08000000 | 0x400 | 0x4000, block, str(self.folder), ctypes.byref(startup), ctypes.byref(proc)):
            self.__exit__(None, None, None)
            raise RuntimeError("Owned Ollama process creation failed")
        self.process = proc.process
        self.pid = proc.pid
        try:
            if not k.AssignProcessToJobObject(self.job, proc.process):
                k.TerminateProcess(proc.process, 1)
                raise RuntimeError("Ollama containment failed")
            if k.ResumeThread(proc.thread) == 0xffffffff:
                raise RuntimeError("Owned Ollama process resume failed")
        except Exception:
            self.__exit__(None, None, None)
            raise
        finally:
            k.CloseHandle(proc.thread)
        return self

    def owns_listener(self):
        """Reject a bind-race winner before sending even a readiness request."""
        import ctypes
        from ctypes import wintypes as w
        size = w.DWORD(0)
        api = ctypes.WinDLL("iphlpapi", use_last_error=True).GetExtendedTcpTable
        api.argtypes = (ctypes.c_void_p, ctypes.POINTER(w.DWORD), w.BOOL, w.ULONG, ctypes.c_int, w.ULONG)
        api.restype = w.DWORD
        api(None, ctypes.byref(size), False, 2, 5, 0)
        buffer = ctypes.create_string_buffer(size.value)
        if api(buffer, ctypes.byref(size), False, 2, 5, 0) != 0:
            raise RuntimeError("Cannot verify owned Ollama listener")
        class TCPROW(ctypes.Structure):
            _fields_ = [(name, w.DWORD) for name in ("state", "local", "port", "remote", "remote_port", "pid")]
        count = ctypes.cast(buffer, ctypes.POINTER(w.DWORD))[0]
        for offset in range(count):
            row = TCPROW.from_buffer(buffer, ctypes.sizeof(w.DWORD) + offset * ctypes.sizeof(TCPROW))
            if row.state == 2 and socket.ntohs(row.port & 0xffff) == 11435:
                if row.pid != self.pid or socket.inet_ntoa(int(row.local).to_bytes(4, "little")) != "127.0.0.1":
                    raise RuntimeError("Ollama listener is not the owned loopback process")
                return True
        return False

    def __exit__(self, *args):
        if self.job:
            self.kernel.CloseHandle(self.job)
            self.job = None
        if self.process:
            self.kernel.WaitForSingleObject(self.process, 3000)
            self.kernel.CloseHandle(self.process)
            self.process = None


def _private_archive(folder, label, raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("Bounded private archive required")
    digest = sha256(raw).hexdigest()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (label + "-" + digest + ".json")
    if not target.exists():
        with target.open("xb") as handle:
            handle.write(raw)
    elif target.read_bytes() != raw:
        raise ValueError("Private archive hash conflict")
    return {"sha256": digest, "name": target.name, "bytes": len(raw)}


class ModelResponseError(ValueError):
    def __init__(self, message, archive):
        super().__init__(message)
        self.archive = archive


class ResourcePressure(RuntimeError):
    pass


def due_events(repository, now):
    from market_intelligence.research_calendar import status
    events = status(repository, now)["upcoming"]
    return [e for e in events if e["instrument_ids"] == ["SASOL"]
        and timedelta(0) < datetime.fromisoformat(e["anchor_at"]) - now <= timedelta(days=7)]


def attempt_id(event_key, now):
    # Daily event budget cannot be reset by changing packet/model/prompt/version.
    return "calendar-ollama-attempt-" + _hash([event_key, now.astimezone(SAST).date().isoformat()])


def reserve(repository, event_id, packet, now):
    rid = attempt_id(packet["event"]["event_key"], now)
    with repository.transaction():
        if repository.backend == "postgresql":
            key = int.from_bytes(sha256(ACCOUNT.encode()).digest()[:8], "big", signed=True)
            repository._job_sql("SELECT pg_advisory_xact_lock(?)", (key,), rows=True)
        prior = repository.paper_record(rid)
        if prior:
            return prior, False
        repository.create_paper_account(ACCOUNT, {"mode": "PAPER", "purpose": "RESEARCH_ONLY"})
        item = {"record_id": rid, "schema": VERSION, "state": "RESERVED_NO_AUTOMATIC_RETRY",
            "event_id": event_id, "event_key": packet["event"]["event_key"],
            "input_id": packet["record_id"], "input_sha256": packet["input_sha256"],
            "reserved_at": now.isoformat(), "model": MODEL, "model_digest": MODEL_DIGEST,
            "prompt_version": packet.get("prompt_version"), "day_sast": now.astimezone(SAST).date().isoformat(),
            "call_budget": 1, "trading_weight": 0, "live_execution": False}
        repository.save_paper_record(rid, ACCOUNT, "calendar-ollama-attempt", now.isoformat(), item)
        return item, True


def _result(repository, reservation, state, now, **fields):
    rid = reservation["record_id"] + "-result"
    with repository.transaction():
        prior = repository.paper_record(rid)
        if prior:
            return prior
        item = {"record_id": rid, "schema": VERSION, "attempt_id": reservation["record_id"],
            "state": state, "received_at": now.isoformat(), "trading_weight": 0,
            "live_execution": False, **fields}
        repository.save_paper_record(rid, ACCOUNT, "calendar-ollama-result", now.isoformat(), item)
        return item


def _session():
    import requests
    session = requests.Session()
    session.trust_env = False  # No inherited proxies, credentials or remote fallback.
    return session


def generate(packet, prompt, schema, executable, folder, *, idle=windows_idle_seconds,
             memory=None, session_factory=_session, owner_factory=OwnedOllama,
             clock=time.monotonic, sleep=time.sleep):
    """Exactly one local generation request; caller must already reserve its budget."""
    if idle() < IDLE_SECONDS:
        raise InterruptedError("User input returned before model start")
    memory = memory or available_memory_bytes
    if memory() < MIN_START_MEMORY:
        raise ResourcePressure("Insufficient free memory before owned model start")
    deadline = clock() + TIMEOUT_SECONDS
    with owner_factory(executable, folder) as owner, session_factory() as session:
        # GET readiness only. No model load/download occurs until the one POST.
        while True:
            if idle() < IDLE_SECONDS:
                raise InterruptedError("User input returned during startup")
            if memory() < MIN_RUNNING_MEMORY:
                raise ResourcePressure("Memory pressure during model startup")
            if clock() >= deadline:
                raise TimeoutError("Local model startup deadline")
            if not owner.owns_listener():
                sleep(.5)
                continue
            try:
                response = session.get(HOST + "/api/tags", timeout=(1, 1), allow_redirects=False)
                response.raise_for_status()
                models = response.json().get("models", [])
                if not any(m.get("name") == MODEL and m.get("digest") == MODEL_DIGEST for m in models):
                    raise ValueError("Installed local model digest mismatch; no download permitted")
                break
            except (ConnectionError, OSError):
                sleep(.5)
            except Exception as exc:
                # requests connection errors have their own non-builtin base.
                if type(exc).__name__ in {"ConnectionError", "ConnectTimeout", "ReadTimeout"}:
                    sleep(.5)
                else:
                    raise
        if idle() < IDLE_SECONDS:
            raise InterruptedError("User input returned before generation")
        if not owner.owns_listener():
            raise RuntimeError("Owned local listener disappeared before generation")
        payload = {"model": MODEL, "prompt": prompt, "format": schema, "stream": False,
            "keep_alive": 0, "options": {"num_thread": 2, "num_gpu": 0,
                "num_ctx": 4096, "num_predict": 400, "temperature": 0}}
        if len(json.dumps(payload).encode()) > MAX_BYTES:
            raise ValueError("Bounded model packet required")
        box = {}
        def request():
            try:
                box["started_at"] = utcnow()
                response = session.post(HOST + "/api/generate", json=payload,
                    timeout=(2, max(1, deadline - clock())), allow_redirects=False, stream=True)
                response.raise_for_status()
                parts, total = [], 0
                for chunk in response.iter_content(4096):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        response.close()
                        raise ValueError("Bounded local response required")
                    parts.append(chunk)
                raw = b"".join(parts)
                box["completed_at"] = utcnow()
                if not 1 <= len(raw) <= MAX_BYTES:
                    raise ValueError("Bounded local response required")
                box["raw"] = raw
            except Exception as exc:
                box["error"] = exc
        thread = threading.Thread(target=request, daemon=True)
        thread.start()
        while thread.is_alive():
            if idle() < IDLE_SECONDS:
                raise InterruptedError("User input returned; owned model process tree terminated")
            if clock() >= deadline:
                raise TimeoutError("Owned local model deadline exceeded")
            if memory() < MIN_RUNNING_MEMORY:
                raise ResourcePressure("Memory pressure; owned model process tree terminated")
            thread.join(.5)
        if idle() < IDLE_SECONDS:
            raise InterruptedError("User input returned before accepting generation")
        if "error" in box:
            raise box["error"]
        raw = box["raw"]
        archive = _private_archive(folder, "response", raw)
        archive["received_at"] = utcnow().isoformat()
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ModelResponseError("Invalid local response envelope", archive) from exc
        if not isinstance(data, dict):
            raise ModelResponseError("Invalid local response envelope type", archive)
        if data.get("done") is not True or data.get("done_reason") == "length":
            raise ModelResponseError("Incomplete local model generation", archive)
        if not isinstance(data.get("response"), str):
            raise ModelResponseError("Missing local model response", archive)
        return raw, data["response"], box["started_at"], box["completed_at"]


def execute(repository, now, folder, executable, *, idle=windows_idle_seconds, memory=None, generator=generate):
    from market_intelligence.calendar_expectations import prepare_input, prompt_for, response_schema, register_response
    if idle() < IDLE_SECONDS:
        return {"state": "WAITING_FOR_10_MINUTES_IDLE", "model_calls": 0, "trading_weight": 0}
    memory = memory or available_memory_bytes
    if memory() < MIN_START_MEMORY:
        return {"state": "WAITING_FOR_MEMORY", "model_calls": 0, "trading_weight": 0}
    events = due_events(repository, now)
    for event in events:
        previous = repository.paper_record(attempt_id(event["event_key"], now))
        if previous:
            continue
        packet = prepare_input(repository, event["record_id"], now)
        prompt = prompt_for(packet)
        schema = response_schema(packet)
        archive = _private_archive(folder, "input", json.dumps({"packet": packet,
            "prompt": prompt, "schema": schema}, sort_keys=True).encode())
        reservation, acquired = reserve(repository, event["record_id"], packet, now)
        if not acquired:
            continue
        if idle() < IDLE_SECONDS:
            return _result(repository, reservation, "CANCELLED_USER_ACTIVE_BEFORE_CALL", utcnow(),
                model_calls=0, input_archive=archive)
        response_archive = None
        try:
            raw, content, started, completed = generator(packet, prompt, schema, executable, folder, idle=idle, memory=memory)
            response_archive = _private_archive(folder, "response", raw)
            report = register_response(repository, packet["record_id"], content,
                model_version=MODEL + "@" + MODEL_DIGEST, request_started_at=started,
                request_completed_at=completed, now=utcnow())
            return _result(repository, reservation, "MODEL_DRAFT_RECORDED_REQUIRES_REVIEW", utcnow(),
                model_calls=1, input_archive=archive, response_archive=response_archive,
                request_started_at=started.isoformat(), request_completed_at=completed.isoformat(),
                domain_result_id=report["run"]["record_id"],
                proposal_ids=[p["record_id"] for p in report["proposals"]])
        except Exception as exc:
            state = ("CANCELLED_USER_RETURNED" if isinstance(exc, InterruptedError) else
                "RESOURCE_PRESSURE" if isinstance(exc, ResourcePressure) else "FAILED_NO_AUTOMATIC_RETRY")
            return _result(repository, reservation, state, utcnow(), model_calls_upper_bound=1,
                input_archive=archive, response_archive=exc.archive if isinstance(exc, ModelResponseError) else response_archive,
                error_type=type(exc).__name__)
    return {"state": "NO_UNRESERVED_DUE_SASOL_EVENT", "model_calls": 0, "trading_weight": 0}


def runner_status(repository, now, *, idle=None, memory=None):
    events = due_events(repository, now)
    attempts = repository.paper_records(ACCOUNT, "calendar-ollama-attempt", as_of=now.isoformat(), limit=1000)
    results = repository.paper_records(ACCOUNT, "calendar-ollama-result", as_of=now.isoformat(), limit=1000)
    if len(attempts) >= 1000 or len(results) >= 1000:
        raise ValueError("Bounded runner status capacity reached")
    idle_value = free = None
    readiness = "RESOURCE_TELEMETRY_UNAVAILABLE"
    try:
        free = (memory or available_memory_bytes)()
        idle_value = (idle or windows_idle_seconds)()
        readiness = ("WAITING_FOR_MEMORY" if free < MIN_START_MEMORY else
            "WAITING_FOR_10_MINUTES_IDLE" if idle_value < IDLE_SECONDS else "READY_FOR_IDLE_DRAFT")
    except Exception:
        pass  # Unavailable telemetry never grants inference eligibility.
    unresolved = sum(not repository.paper_record(a["record_id"] + "-result") for a in attempts)
    return {"state": "LOCAL_CALENDAR_DRAFT_RUNNER_ONLY", "due_events": len(events),
        "reserved_today": sum(bool(repository.paper_record(attempt_id(e["event_key"], now))) for e in events),
        "model": MODEL, "model_digest": MODEL_DIGEST, "endpoint": HOST,
        "idle_seconds_required": IDLE_SECONDS, "model_calls_on_read": 0, "trading_weight": 0,
        "minimum_start_free_ram_bytes": MIN_START_MEMORY, "abort_free_ram_below_bytes": MIN_RUNNING_MEMORY,
        "readiness_state": readiness, "resources_ready": readiness == "READY_FOR_IDLE_DRAFT",
        "available_physical_ram_gib": round(free / GIB, 2) if free is not None else None,
        "minimum_start_free_ram_gib": 7, "observed_idle_seconds": round(idle_value, 1) if idle_value is not None else None,
        "total_reservations": len(attempts), "total_results": len(results),
        "unresolved_reservations": unresolved,
        "completed_generation_calls": sum(r.get("model_calls", 0) for r in results),
        "uncertain_generation_call_upper_bound": unresolved + sum(r.get("model_calls_upper_bound", 0) for r in results),
        "latest_states": [{"state": r["state"], "received_at": r["received_at"]} for r in results[:5]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "dry-run", "run"))
    args = parser.parse_args()
    from scripts.run_local_pc import FOLDER, start_database
    from scripts.local_runtime import configuration, verify_database, process_lock
    from ai_config import project_environment
    from runtime_persistence import runtime_repository
    env = project_environment()
    env.update(json.loads((FOLDER / "environment.json").read_text()))
    now = utcnow()
    receipt = json.loads((FOLDER / "bootstrap-acceptance.json").read_text())
    url, identity = configuration(env, receipt, now)
    start_database()
    verify_database(url, identity)
    repository = runtime_repository(database_url=url)
    try:
        if args.command != "run":
            result = runner_status(repository, now)
        elif windows_idle_seconds() < IDLE_SECONDS:
            result = {"state": "WAITING_FOR_10_MINUTES_IDLE", "model_calls": 0, "trading_weight": 0}
        else:
            below_normal()
            executable = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"
            if not executable.is_file():
                raise ValueError("Existing official installed Ollama required")
            with process_lock(FOLDER / "heavy-research.lock"):
                result = execute(repository, now, FOLDER / "calendar-ollama", executable)
        # Output is bounded operational metadata; source text/raw responses stay private.
        print(json.dumps({k: result[k] for k in ("state", "model_calls", "model_calls_on_read", "model_calls_upper_bound",
            "trading_weight", "due_events", "reserved_today", "received_at", "readiness_state", "resources_ready",
            "available_physical_ram_gib", "minimum_start_free_ram_gib", "observed_idle_seconds") if k in result}))
    finally:
        repository.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"state": "CALENDAR_OLLAMA_BLOCKED", "error_type": type(exc).__name__}))
        raise SystemExit(1)
