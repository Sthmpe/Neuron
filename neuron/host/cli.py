"""The host program: pretends to be the phone.

  python3 -m neuron.host.cli send "find leads" [--delay 30] [--watch]
  python3 -m neuron.host.cli watch <task_id> [--auto-approve | --auto-reject]
  python3 -m neuron.host.cli status [<task_id>]
  python3 -m neuron.host.cli permissions
  python3 -m neuron.host.cli approve <permission_id>
  python3 -m neuron.host.cli reject <permission_id>
  python3 -m neuron.host.cli network on|off        (simulated switch)
  python3 -m neuron.host.cli report <task_id>
"""
import argparse
import sys
import time

from .client import BrainUnreachable, HostClient


def stamp(t):
    return time.strftime("%H:%M:%S", time.localtime(t))


def print_steps(detail):
    t = detail["task"]
    print(f"Task {t['id']}  [{t['status']}]  {t['goal']}")
    for s in detail["steps"]:
        kind = "needs internet" if s["needs_internet"] else "offline"
        flag = " SENSITIVE" if s["sensitive"] else ""
        print(f"  {s['no']:>2}. {s['status']:<18} ({kind}{flag}) {s['title']}")


def watch(client, task_id, auto=None, out=print):
    """Show progress until the task ends. auto: None=ask, True=approve, False=reject."""
    last = 0
    while True:
        try:
            for e in client.events(task_id, last):
                last = e["id"]
                out(f"  {stamp(e['at'])}  {e['message']}")
            for p in client.permissions("pending"):
                if p["task_id"] != task_id:
                    continue
                if auto is None:
                    ans = input(f"  >>> PERMISSION NEEDED: step {p['step_no']} '{p['description']}'. Approve? [y/n] ")
                    ok = ans.strip().lower().startswith("y")
                else:
                    ok = auto
                out(f"  >>> host {'APPROVES' if ok else 'REJECTS'} step {p['step_no']}: {p['description']}")
                client.decide(p["id"], ok)
            if client.task(task_id)["task"]["status"] in ("done", "failed"):
                for e in client.events(task_id, last):
                    last = e["id"]
                    out(f"  {stamp(e['at'])}  {e['message']}")
                return
        except BrainUnreachable:
            out("  (brain not reachable - will keep trying)")
        time.sleep(0.3)


def main(argv=None):
    ap = argparse.ArgumentParser(description="NEURON host (the pretend phone)")
    ap.add_argument("--brain", default="http://127.0.0.1:8765")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("send"); p.add_argument("goal"); p.add_argument("--delay", type=float, default=0)
    p.add_argument("--watch", action="store_true")
    p = sub.add_parser("watch"); p.add_argument("task_id")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--auto-approve", action="store_true"); g.add_argument("--auto-reject", action="store_true")
    p = sub.add_parser("status"); p.add_argument("task_id", nargs="?")
    sub.add_parser("permissions")
    p = sub.add_parser("approve"); p.add_argument("id", type=int)
    p = sub.add_parser("reject"); p.add_argument("id", type=int)
    p = sub.add_parser("network"); p.add_argument("state", choices=["on", "off"])
    p = sub.add_parser("report"); p.add_argument("task_id")
    a = ap.parse_args(argv)
    c = HostClient(a.brain)
    try:
        if a.cmd == "send":
            d = c.send_task(a.goal, a.delay)
            print_steps(d)
            if a.watch:
                watch(c, d["task"]["id"])
                print(c.report(d["task"]["id"])["text"])
        elif a.cmd == "watch":
            watch(c, a.task_id, True if a.auto_approve else False if a.auto_reject else None)
            print(c.report(a.task_id)["text"])
        elif a.cmd == "status":
            if a.task_id:
                print_steps(c.task(a.task_id))
            else:
                for t in c.tasks():
                    print(f"{t['id']}  [{t['status']}]  {t['goal']}")
        elif a.cmd == "permissions":
            for p in c.permissions("pending"):
                print(f"#{p['id']}  task {p['task_id']} step {p['step_no']}: {p['description']}")
        elif a.cmd in ("approve", "reject"):
            print(c.decide(a.id, a.cmd == "approve"))
        elif a.cmd == "network":
            print(c.set_network(a.state == "on"))
        elif a.cmd == "report":
            print(c.report(a.task_id).get("text", "no such task"))
    except BrainUnreachable as e:
        sys.exit(f"Cannot reach the brain at {a.brain}: {e}")


if __name__ == "__main__":
    main()
