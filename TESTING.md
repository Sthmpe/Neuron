# Testing NEURON yourself

This is the owner test: install NEURON on a computer at home, open it on your phone, give it real work, and check what comes back. No coding needed. Every step says what you should see, so you can tell if something is wrong.

## What you need

- A computer running **Linux** (tested: Ubuntu 24.04). Windows and Mac are **not supported yet**; they will only be marked supported after they have been tested.
- At least **4 GB of memory** in the computer. 8 GB or more gives a smarter model, 16 GB or more gives the smartest one.
- About **10 GB of free disk space**.
- Internet **once**, for the install. After that NEURON works with the internet switched off.
- Your phone on the **same Wi-Fi** as the computer.

## 1. Install (one command, about 15 to 40 minutes)

Open a terminal on the computer, then:

```
git clone https://github.com/Sthmpe/Neuron.git
cd Neuron
bash scripts/install.sh
```

It may ask for your computer password (to install system packages). You should see these numbered lines:

1. **Memory**: how much the computer has and how much is kept free for the computer itself.
2. **Tier**: which model was picked for that amount of memory, its size and licence.
3. **Downloading** the model, then **checksum matches the frozen value**. If the checksum does not match, the file is deleted and nothing is installed. That is on purpose.
4. **Self-test**: the model answers a small sum (it must say 42), the safe box for running code says 42, and a list of any tools that are missing.
5. **Settings written**.

Then NEURON starts and prints two lines (if you started it as a service, see them with `journalctl --user -u neuron`):

```
NEURON is running. On your phone (same Wi-Fi) open: http://192.168.x.x:8642
Pairing code: 123456  (valid 10 minutes ...)
```

If the install stops, it says why in one sentence. Send that sentence to the developer.

Want to see what it would pick before installing? `bash scripts/install.sh --plan`

## 1b. Install on Windows 10 or 11 (UNVERIFIED: please test and report back)

NEURON runs inside Ubuntu on WSL2 (Windows' built-in Linux). This path has **not been run on a Windows computer yet**;
your report decides whether it works. Note anything that differs from what is written here.

You need: Windows 10 version 2004 or newer (or Windows 11), virtualisation switched on in the BIOS, at least 8 GB of
memory (6 GB works only for the smallest tier), 15 GB free on drive C, and the internet for the install.

1. Download the repository as a ZIP from GitHub (green **Code** button, **Download ZIP**) and unzip it, or copy
   `scripts\install-windows.ps1` from it to your Desktop.
2. Open **PowerShell** (Start menu, type PowerShell, normal window, not "Run as administrator").
3. Go to the folder and allow this one script for this window only:
   ```
   cd $HOME\Desktop
   Set-ExecutionPolicy -Scope Process Bypass
   .\install-windows.ps1 -Plan
   ```
   **Check:** it prints your Windows version and build, memory, free disk, "hardware virtualisation: on", the WSL memory
   limit (it keeps max(3 GB, 30%) for Windows), the expected tier, and either "mirrored networking" (Windows 11 22H2
   or newer) or "port forwarding". Nothing is changed by `-Plan`. Send me these lines.
4. Run it for real: `.\install-windows.ps1`. It asks before each of these, and you can say no:
   - installing WSL2 and Ubuntu 24.04 (Windows asks for administrator approval; then a restart is usually needed:
     restart, open **Ubuntu** once from the Start menu, choose an Ubuntu user name and password, run the script again);
   - writing `C:\Users\<you>\.wslconfig` with the memory limit (your old file is kept as `.wslconfig.neuron-backup`)
     and restarting WSL;
   - inside Ubuntu: your Ubuntu password for system packages, and a GitHub sign-in because the repository is private
     (use your GitHub user name and a personal access token as the password);
   - a Windows Firewall rule for port 8642 on private (home) networks only (administrator approval).
5. **Check:** the Ubuntu part prints the same numbered steps as the Linux install (memory, tier, download, checksum,
   self-test 42, sandbox passed). The tier should match what `-Plan` predicted.
6. Start NEURON: answer yes at the end, or later run `C:\Users\<you>\NEURON\Start-NEURON.ps1`. With port forwarding,
   Windows asks for administrator approval at each start (WSL's address changes after a restart).
7. On the phone (same Wi-Fi) open the address it prints, which is your **Windows** address, and pair as in step 2 below.

Report back: the `-Plan` lines, where it stopped if it did (copy the message), whether the phone connected, and
whether one task from section 3 finished. Until then Windows stays marked **not verified**.

## 2. Pair your phone (once)

1. On the phone, open the address it printed (for example `http://192.168.1.20:8642`).
2. Type the 6-digit pairing code and tap **Pair this phone**.

You should see "What should NEURON do?". 

Check these too:
- A wrong code says "wrong or expired code". After 5 wrong codes it stops accepting codes for a while.
- A code works only once. A second phone needs a new code: on the computer run `~/.neuron/start.sh code`.

## 3. Give it real work

Type the goal in your own words, attach files if needed, tap **Start**. The job page shows each step, who did it (the model, a fixed template, or plain code), how it was checked, and the evidence. When it finishes, the badge says **Done and checked**, **Partly done** or **Not done**, and the files are under **Results** to download.

Try one of each:

| Try this | Attach | A good result |
|---|---|---|
| "Make sales.xlsx with the rows on a sheet Data and a sheet Summary with total sales per region and a Total row, using formulas." | a CSV of sales | Opens in Excel or Google Sheets, Summary cells are formulas, totals are right. |
| "Write proposal.docx: a proposal for a school library with the headings Background, Plan, Budget, about 500 words, and a budget table with a total." | nothing | Opens in Word, has those headings, the table total adds up. |
| "Make pitch.pptx with 5 slides about a solar kiosk business, at most 4 bullets per slide." | nothing | Opens in PowerPoint, 5 slides, at most 4 bullets on each. |
| "Using the attached report, what was the water loss in 2025 and on which page is it?" | a PDF | An answer with the page number and an exact quote that is really on that page. |
| "The tests fail. Find the bug and fix it without changing the tests." | your project as a .zip | The step says the project's own tests now pass. Download the changed files. |
| "Build a small app to track my shop's stock and sales." | nothing | **Open the app** appears; the app works on the phone. |

Honest limits right now:
- Small computers are slow. A 4 GB machine can take many minutes per step.
- Built apps are simple data apps (lists, forms, totals, logins). Rules like "a sale reduces stock" are not supported yet.
- NEURON tells you when it is missing a tool instead of pretending. That is a correct answer, not a crash.

## 4. Offline test

1. Unplug the internet from your router (keep the Wi-Fi itself on), or switch the computer's internet off but keep it on the same network as the phone.
2. The top-right label on the phone page changes to **Offline, working locally**.
3. Give it any job from the table above. It should work the same.

## 5. Stop and resume test

1. Start a long job (the app or the Word document).
2. While it is working, turn the computer off, or close NEURON with Ctrl+C.
3. Start NEURON again: `~/.neuron/start.sh`
4. Open the job on the phone. It continues from where it was; finished steps are not redone.

You can also tap **Stop** on the job page and later **Resume**.

## 6. Approvals

Anything NEURON marks as sensitive (for example sending a message) waits for you. The job shows **Needs your OK** with **Approve** and **Reject**. Nothing sensitive happens before you tap Approve.

## 7. Status

Tap the top-right label. You see: internet on or off, memory free, which model is in memory, processor load, and what NEURON is working on.

## Security, plainly

- Only paired phones can use NEURON. Pairing codes expire after 10 minutes and work once. Phone keys are stored scrambled (hashed) on the computer.
- By default the phone talks to the computer over **plain HTTP on your home Wi-Fi**. Someone else on the same Wi-Fi could read the traffic.
- To encrypt it, start NEURON with `~/.neuron/start.sh --https`. NEURON makes its own certificate on your computer and prints its fingerprint. The phone will warn that it does not know the certificate: open the certificate details, check the SHA-256 fingerprint matches the printed one, then continue. After that the traffic is encrypted. (Pair again after switching, because the address starts with https.)
- Code that NEURON writes or fixes runs inside a locked box with no internet and no access to your other files.
- To remove all paired phones: delete `~/.neuron/devices.json` and restart NEURON.

## If something goes wrong

- NEURON's own messages: the terminal where it runs, or `journalctl --user -u neuron` if you enabled the service.
- Model server logs: `~/.neuron/logs/`
- Each job's files and notes: `~/.neuron/jobs/<job id>/`

Send the one-sentence error and the job id to the developer.

## What has been tested, and where

| Part | Tested how | Where |
|---|---|---|
| Installer | Full run: packages, Python libraries, checksum check, model self-test, sandbox self-test | Ubuntu 24.04 in a cloud container (not yet on a home PC) |
| Download resume and wrong-checksum refusal | Automatic test with a server that cuts the connection | same |
| Pairing, security, jobs, uploads, downloads, approvals, follow-ups, previews, HTTPS, restart | Automatic tests | same |
| Phone page | Automatic test in a real browser at phone size: pair, goal with a file, finished job, download, status | same (Chromium, not a real phone yet) |
| Windows 10/11 (WSL2) | Installer written; decision rules unit-tested; **never run on Windows** | Waiting for your test (section 1b) |
| Stock Ubuntu desktop (cgroup v2, AppArmor) | Memory limits through systemd and the AppArmor offer are written; this test machine uses older cgroups as root, so they were not exercised | Waiting for a real Ubuntu PC |
| Mac | Not tested | Not supported yet |
