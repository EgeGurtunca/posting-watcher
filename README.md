# posting-watcher

![tests](https://github.com/EgeGurtunca/posting-watcher/actions/workflows/test.yml/badge.svg)

Reads the internship postings that land in my inbox, decides which ones are technical, and sends those to
my phone on Telegram, with the deadline and how to apply. Everything runs on my laptop with a local model.

I live in Tekirdağ and study in Istanbul, so remote and hybrid internships matter to me, and on my
university's CO-OP mailing list they close four or five days after they are posted. In July an online
AI internship came through that fit me better than anything since, and I saw it after the deadline. This is the fix.

```
🆕 [poster] · [position] · [company]
📍 [location] · [mode]
⏰ son gün: [date] ([countdown])
✉️ [apply to] · konu: "[subject line]"
```

It is the fourth project in a series where I work through the LLM stack one layer at a time; the earlier
ones are [bau-mevzuat-rag](https://github.com/EgeGurtunca/bau-mevzuat-rag) (retrieval) and
[sakila-sql-agent](https://github.com/EgeGurtunca/sakila-sql-agent) (an agent loop). This one is about the
unglamorous parts of putting a model in front of real data: getting the data in, structured extraction,
deciding in code, and failing loudly.

**Stack:** Python 3.12 (standard library only) · Ollama (`gemma4:12b`) · Power Automate · Gmail over IMAP ·
SQLite · Telegram Bot API · pytest

## How it works

```
school mailbox ──Power Automate──► <time>-<guid>.eml, as an attachment ──► a Gmail used only for this

Task Scheduler, every hour ──► python -m watcher.run
   unread bridge mails ──IMAP──► their .eml attachments into the watch folder
   new .eml from a known sender? ──► start Ollama ──► gemma4 lists the postings in the mail
       each posting: company, title, kind, technical, mode, location, pay, deadline sentence, how to apply
   ──► the code decides: technical, and a co-op, internship or programme, and the deadline has not passed
   ──► Telegram
   21:00 ──► the day's digest            Monday ──► "still running" with last week's counts
   any failure ──► an alert (at most one per kind of failure per day)
```

**Getting the mail.** This took more attempts than anything else. The plan was Microsoft Graph with my own
app registration, but my university's Microsoft 365 tenant returns 401 on the Entra portal, so students
cannot register apps. A Power Automate flow in the same tenant can read my mail, though: "When a new email
arrives" from the CO-OP address, then "Export email", which gives the whole mail as one `.eml`. Getting that
file onto the laptop was the hard part:

- OneDrive: "Create file" works, but then the OneDrive app has to run on the laptop all the time to sync it.
- rclone, to copy just that folder: the tenant asks for admin consent, so no.
- My Outlook.com address: Microsoft turned off password logins for IMAP, and OAuth means an app registration again.
- A Gmail account used only for this: the flow mails each `.eml` to it as an attachment, and
  [watcher/gmail.py](watcher/gmail.py) copies the attachments into the watch folder with `imaplib`. One app
  password in `.env`, for an inbox that holds nothing else. This is what runs.

From there, reading mail is reading files with the standard library's `email` package. The flow still saves
a copy to OneDrive, which doubles as an archive.

**The model reads, the code decides.** The model fills in a fixed set of fields, and Ollama's structured
outputs constrain its answer to a JSON schema, so it cannot return broken JSON or a kind outside the list.
Whether a posting deserves a message is one line of code in [watcher/rules.py](watcher/rules.py), which I can
read and test. I learned this in bau-mevzuat-rag: a model told "say not found if the documents don't answer"
wrote polite explanations instead; a model asked to fill in a field fills it in.

**Deadlines.** The model copies the deadline sentence word for word and
[watcher/deadline.py](watcher/deadline.py) turns it into a date, because the rules are easy to get wrong and
easy to test: "27 Eylül PAZAR tarihine **kadar**" includes that day, "26 Eylül CUMARTESİ tarihinden
**önce**" means the 25th, the year is never written, and three mails in three months left out the day
number entirely ("Eylül CUMARTESİ tarihinden önce", so: the first Saturday of September after the mail
arrived). Python's `str.lower()` also turns "SALI" (Tuesday) into "sali" instead of "salı", which breaks
the weekday match; Turkish needs its own lowercasing.

**Failing loudly.** A watcher that fails silently looks exactly like a quiet week, and a quiet week is when I
would stop checking. So: a missing watch folder is an error, not an empty inbox (`Path.glob` on a folder
that does not exist returns nothing, which is exactly what a broken sync would look like); a bridge mail is
marked read only after its file is on disk; every failure, a rejected Gmail login included, sends an alert;
and the Monday heartbeat warns when no mail file has arrived for seven days, which catches a broken flow even
when nothing crashes. Ollama is started only when there is a mail to read and
stopped again afterwards, so the GPU stays idle the rest of the time.

## Evaluation

I exported every mail the CO-OP list sent between July and September 2026: 54 mails, 35 of them co-op
postings, the rest other internships, programmes and announcements. The export is not in the repo (it has
staff names and addresses); the labels are, in [eval/gold.jsonl](eval/gold.jsonl): for each mail whether it
should trigger a message, and the kind, mode and deadline of the posting. I drafted them with an AI assistant
and checked them against the mails, the borderline ones (7) one by one.

```bash
python -m eval.run_eval --systems keywords,gemma4:12b,qwen3.5:9b,qwen2.5:7b
```

| system | technical postings caught (recall) | messages that were right (precision) | mode | deadline | s / mail |
|---|---|---|---|---|---|
| keywords, no LLM | 18/23 = 0.78 | 0.90 | 0.83 | 0.98 | 0 |
| `qwen2.5:7b` | 0.74 | 0.74 | 0.78 | 0.96 | 2.1 |
| `qwen3.5:9b` | 0.78 | **1.00** | 0.92 | 0.96 | 2.9 |
| **`gemma4:12b`** | **22/23 = 0.96** | 0.96 | **1.00** | **1.00** | 4.0 |

`gemma4:12b` makes the right call on all 47 clear-cut mails; its one miss and its one false alarm are both
on mails I marked borderline. It is the default.

- **The baseline is worth having.** Subject tags (FİZİKSEL, HİBRİT, ONLINE), title keywords and a deadline
  regex already get 98% of deadlines, because the CO-OP format is regular. They miss postings whose subject
  has no technical word (a software company's internship programme, two engineering programmes) and
  are fooled by "Yazılım" in the subject of what turns out to be an IT recruitment job. The model earns its
  four seconds exactly on what the subject line doesn't say.
- **The Turkish I problem cut both ways.** Turkish lowercasing fixed the weekdays, then broke my baseline:
  it turns "IT" into "ıt", "AI" into "aı" and "ONLINE" into "onlıne". The first baseline run missed the
  very posting this project exists for.
- **My prompt caused the first round of false alarms.** gemma4's first run had eight. I had written that a
  programme "aimed at engineering students" counts as technical, and the model applied that to job
  postings that ask for engineering students (insurance operations, factory operations, intellectual
  property). "Judge the work the person will do, not who may apply" fixed all of them.
- **The model was right and my label was wrong.** A posting with "computer engineering" in its title turned
  out to be product listings and SEO for e-commerce. I had labelled it from the title; the model read the
  duties. A label is an assumption too.
- **The honest caveat.** The prompt and the labels were refined on these same 54 mails, so 0.96 is the score
  on the data I tuned against. The real test is the mail that arrives from October on, and I will add those
  numbers here.

## Running it

1. Install [Ollama](https://ollama.com) and `ollama pull gemma4:12b` (7.6 GB). No Python packages are needed. On Windows, if
   `python` opens the Microsoft Store instead, turn off its alias (Settings > Apps > Advanced app settings > App
   execution aliases) or run Python by its full path.
2. Make a Telegram bot with @BotFather, copy `.env.example` to `.env` and put the token in. Send the bot any
   message, run `python -m watcher.notify` to print your chat id, add it to `.env`, and run it again: a test
   message arrives.
3. In Power Automate (make.powerautomate.com), create an automated cloud flow: trigger "When a new email
   arrives (V3)" with From set to the senders you want, then "Export email (V2)" with the trigger's Message
   Id, then "Send an email (V2)" to a Gmail account you keep for this, with the subject `posting-watcher` and
   one attachment: name `concat(formatDateTime(utcNow(),'yyyyMMdd-HHmmss'),'-',guid(),'.eml')`, content
   `body('Export_email_(V2)')` (the action's name in your flow's language).
4. Turn on 2-step verification for that Gmail account, create an app password, and put `GMAIL_USER`,
   `GMAIL_APP_PASSWORD` and a local `WATCH_FOLDER` (it is created on the first run) in `.env`. If you would
   rather sync a OneDrive folder, have the flow "Create file" there instead, leave the Gmail lines out and point
   `WATCH_FOLDER` at the synced folder.
5. Run every hour and at logon, with `pythonw` so no console window flashes:

```powershell
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
$action = New-ScheduledTaskAction -Execute $py -Argument "-m watcher.run" -WorkingDirectory (Get-Location)
$triggers = @((New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)),
              (New-ScheduledTaskTrigger -AtLogOn))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "posting-watcher" -Action $action -Trigger $triggers -Settings $settings
```

Run it from the repo folder. Errors also go to `data/watcher.log`, and the database of what was read and sent
is `data/watcher.db`.

## Tests

```bash
pytest
```

42 tests, no network: every deadline phrasing from the three months of mail, the notify rule, reading
plain and HTML-only `.eml` files (a subject folded the Exchange way, the same mail saved twice, read once),
the Gmail bridge against a fake IMAP server (attachments saved before the mail is marked read, only `.eml`
files, no file names that escape the folder), the extraction schema, the baseline, the eval scoring, and the
run loop with fakes for the model and Telegram (a posting is notified once, a crash leaves the mail unread
for the next run, a missing folder is an error, the model is not started when there is no new mail, the digest and the
heartbeat go out once, a message longer than Telegram's 4096-character limit is cut instead of refused).

## What's next

- Run it live and report the October numbers above
- LinkedIn job alerts: one mail carries several postings, which the extraction already returns as a list
- Poster-only mails: three of the 54 were just an image, and gemma4 can read images
