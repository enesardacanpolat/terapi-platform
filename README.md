# iyi — Therapy Platform

A mobile-friendly web MVP built with FastAPI and PostgreSQL. The interface is in Turkish and uses warm green, coral, and yellow tones. The frontend does not require a separate build step.

## Features

- Mood selection → multiple support preferences → verified professionals with matching areas of practice. Matching uses transparent rules; it does not provide a diagnosis or clinical assessment.
- Professional profiles with education, areas of practice, biographies, session prices, session duration, and reviews from clients who have completed a session. Client names are not displayed with reviews.
- Separate client and professional accounts, each with an appointment dashboard.
- Weekly availability and bookable sessions up to 90 days ahead, using the `Europe/Istanbul` time zone.
- Appointment request → professional approval → completion marked by the professional after the session ends → one review per client and professional.
- Either participant can cancel a future appointment, making the time slot available again.
- PostgreSQL exclusion constraints prevent overlapping appointments for both clients and professionals, including concurrent booking requests.
- Mood and support preferences are shared with the professional only when the client selects the sharing checkbox during booking. Credential numbers are not displayed on public profiles.
- Changing a professional's title, education, or credential number removes their verified status. Removing availability rules does not cancel existing appointments.

## Run locally

From the project directory, activate the existing virtual environment:

```sh
source .venv/bin/activate
```

For a fresh installation, create the virtual environment first, install the dependencies, and copy the environment template:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Do not overwrite an existing `.env` file. Configure `DATABASE_URL`, `POSTGRES_PASSWORD`, and `SECRET_KEY` in your local `.env` file. The password in `DATABASE_URL` must match `POSTGRES_PASSWORD`, and the database connection must match the Docker Compose settings. Never commit real credentials.

Start the database, apply migrations, and run the application:

```sh
docker compose up -d db
alembic upgrade head
DEBUG=false uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Application: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Use a strong `SECRET_KEY`. Keep `DEBUG` and `DEMO_MODE` disabled outside local development. Changing `POSTGRES_PASSWORD` in `.env` does not change the password of an existing PostgreSQL user; update the database password separately when rotating credentials.

## Try the demo

Stop any application server already using port 8000, then run:

```sh
DEBUG=false .venv/bin/python scripts/demo.py
```

The demo creates a separate, randomly named schema in the same PostgreSQL database. It does not modify existing application records. A banner identifies the profiles as examples, and the demo schema is removed when the script shuts down normally. Sample education details are not real professional credentials. The demo server is accessible only from the local computer.

The following accounts are disposable demo accounts, not production credentials:

| Account | Email | Password |
| --- | --- | --- |
| Client | danisan@iyi.example | IyiDemo2026! |
| Deniz Yılmaz — professional | uzman1@iyi.example | IyiDemo2026! |
| Ece Demir — professional | uzman2@iyi.example | IyiDemo2026! |
| Can Aydın — professional | uzman3@iyi.example | IyiDemo2026! |

Select a mood and support preferences, open a professional's profile, choose a time slot for tomorrow, and book using the client account. Sign out and sign in as the corresponding professional to approve the appointment. Past time slots are not displayed. A new browser tab may require signing in again.

## Professional verification

Professionals can create their profiles after registration, but their profiles remain unavailable for public discovery and new bookings until verified. This version does not include an administrator web dashboard.

After manually reviewing education and professional credentials outside the application, an operator can use the local management command:

```sh
DEBUG=false .venv/bin/python scripts/verify_therapist.py PROFILE_UUID --credentials-reviewed
```

To revoke verification:

```sh
DEBUG=false .venv/bin/python scripts/verify_therapist.py PROFILE_UUID --revoke
```

Replace `PROFILE_UUID` with the profile's `id` returned by `/api/therapists/me` when authenticated as the professional. There is no API that allows users to verify themselves.

Legacy reviews without an associated client are preserved, but excluded from public reviews and rating averages.

## Tests

```sh
DEBUG=false .venv/bin/python -m unittest discover -s tests -v
node --check app/static/app.js
```

The tests apply all migrations from scratch in a separate PostgreSQL schema, start a temporary API server, and remove their schema afterward. The database user must have permission to create schemas. Existing application records are not modified.

Coverage includes concurrent bookings, overlapping appointments with different professionals, direct database overlap protection, role and ownership checks, cancellations, past time slots, time off, verification, and review eligibility.

## Current scope and next steps

This is a locally runnable appointment-booking MVP. It does not yet include payment processing, video calls, email or SMS notifications, password resets, email verification, administrator or moderation dashboards, or native iOS and Android apps.

The message indicating that an appointment request has been sent to a professional means that the record is visible in their dashboard; no external notification is sent. The dashboard's refresh button retrieves the latest records.

Before launching with real users, complete the personal-data handling processes, user notices and consent flows, professional verification workflow, retention and deletion rules, access logging, rate limiting, HTTPS configuration, and backup and recovery procedures. Although client names are hidden in public reviews, clients may include personal information in their review text; a moderation workflow has not yet been implemented. This version should not be considered production-ready.

A future mobile application can use the same `/api` endpoints. Further development can build on the selected mobile framework and payment and video-call services.
