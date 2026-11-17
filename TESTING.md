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
- The phone talks to the computer over **plain HTTP on your home Wi-Fi**. Someone else on the same Wi-Fi could read the traffic. Use it on a home network you trust. Encrypted connections (HTTPS) are planned.
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
| Pairing, security, jobs, uploads, downloads, approvals, restart | Automatic tests | same |
| Phone page | Automatic test in a real browser at phone size: pair, goal with a file, finished job, download, status | same (Chromium, not a real phone yet) |
| Windows, Mac | Not tested | Not supported yet |
