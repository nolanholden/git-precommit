#!/usr/bin/env python3

import concurrent.futures
import os
import shlex
import subprocess
import sys

REPO_NAME = 'YOUR_REPO_NAME'
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO_ROOT)

FROM_GIT = len(sys.argv) > 1 and sys.argv[1] == '--from-git'

# TODO: decide what people like better. I think hidden slowness is annoying,
# and never run quietly.
#
# QUIET = FROM_GIT
QUIET = False

##########################################
# Commands to run in parallel.
##########################################
PRE_COMMIT_CHECKS = [
    dict(cwd='chatbot', cmd=['pnpm', 'format:check']),
    dict(cwd='website', cmd=['pnpm', 'format:check']),
]

# ANSI colors & control sequences
RESET = '\033[0m'
RED = '\033[31;1m'
GREEN = '\033[32;1m'
YELLOW = '\033[33;1m'
BLUE = '\033[34;1m'
FAINT = '\033[2m'
CLEAR_LINE = '\033[K'


def eprint(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)


def run_cmd_inherit_stdx(cmd, *, cwd=None, shell=False, check=False):
    r = subprocess.run(cmd, cwd=cwd, shell=shell, check=check)
    return r.returncode, r.stdout, r.stderr


def run_cmd_combined_stdout(cmd, *, cwd=None, shell=False, check=False):
    r = subprocess.run(cmd, cwd=cwd, shell=shell, check=check,
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, r.stdout


def fulfill_prerequisities():
    # pnpm version check
    # NOTE: disabled for speed.
    #
    # pnpm_version = run_cmd_inherit_stdx(['pnpm', '--version'], check=True)[1].strip()
    # assert pnpm_version == '8.6.3', f"incorrect pnpm version, not {pnpm_version}"

    if not os.path.isdir('chatbot/node_modules'):
        eprint(f"{YELLOW}[{REPO_NAME}/chatbot]{RESET} {FAINT}pnpm install{RESET}")
        run_cmd_inherit_stdx(cwd='chatbot', cmd=['pnpm', 'install'])

    if not os.path.isdir('website/node_modules'):
        eprint(f"{YELLOW}[{REPO_NAME}/website]{RESET} {FAINT}pnpm install{RESET}")
        run_cmd_inherit_stdx(cwd='website', cmd=['pnpm', 'install'])


def run_precommit_checks(executor: concurrent.futures.ProcessPoolExecutor):
    checks = PRE_COMMIT_CHECKS

    # Start running ASAP.
    futures = [executor.submit(run_cmd_combined_stdout, **args)
               for args in checks]

    num_output_lines = 1 + len(checks)
    cwds = [args['cwd'] for args in checks]
    check_cmds = [shlex.join(args['cmd']) for args in checks]

    def fmt_rc(rc):
        if rc is None:
            return f'{FAINT}?{RESET}'
        return f'{GREEN}✓{RESET}' if rc == 0 else f'{RED}✗{RESET}'

    def print_status(clear):
        rcs = [(f.result()[0] if f.done() else None) for f in futures]
        any_fail = any(rcs)
        if any_fail:
            header_line = f"{BLUE}pre-commit checks:{RESET} {RED}[FAILED]{RESET}"
        else:
            header_line = f"{BLUE}pre-commit checks:{RESET}"
        status_lines = [
            f"""{BLUE}[{REPO_NAME}/{cwd}]{RESET} {fmt_rc(rc)}{FAINT}: {cmd}{RESET}{f'  (exit {rc})' if rc else ''}{RESET}""" for cwd, cmd, rc in zip(cwds, check_cmds, rcs)]
        output_lines = [header_line, *status_lines]
        assert len(output_lines) == num_output_lines
        progress = f'{term_clear_lines(len(output_lines)) if clear else ""}{term_print_lines(output_lines)}'
        sys.stderr.write(progress)

    if QUIET:
        concurrent.futures.wait(futures)
        any_failed = any(f.result()[0] for f in futures)
        if any_failed:
            print_status(clear=False)
    else:
        print_status(clear=False)
        for _ in concurrent.futures.as_completed(futures):
            print_status(clear=True)

    # If there any failed commands, print stdout/err of failed commands:
    failures = False
    for f, cwd, cmd in zip(futures, cwds, check_cmds):
        rc, stdouterr = f.result()
        if rc:
            failures = True
            eprint()
            eprint(
                f'{YELLOW}stdout/stderr{RESET} of {BLUE}[{REPO_NAME}/{cwd}]{RESET} {FAINT}{cmd}{RESET}:')
            eprint('-' * 80)
            sys.stderr.write(stdouterr)
            eprint('-' * 80)

    if failures:
        eprint(f"{RED}pre-commit checks failed{RESET}")
        sys.exit(1)


def term_clear_lines(n):
    # clear the last n lines
    # - \033[1A: move cursor up 1 line
    # - \033[2K: clear line
    return '\033[1A\033[2K' * n


def term_print_lines(lines):
    lf = '\n'
    return f'{lf.join(lines)}\n'


def main():
    fulfill_prerequisities()
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(PRE_COMMIT_CHECKS)) as executor:
        run_precommit_checks(executor)


if __name__ == '__main__':
    main()
