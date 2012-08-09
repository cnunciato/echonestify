echonestify
===========

Processes RDS extracts for EchoNest ingestion.

### Usage

    Echonestifier "C:\path\to\extract.xml" "D:\path\to\output.json"

While this is running, go grab a sandwich.  It'll be a while.

This'll generate the JSON file for tracks.  Then, you'll need to run Echonest's validator (which requires Python):

    python json_validator_v1.0.0.6.py "D:\path\to\output.json" "track"

This runs a bit quicker -- latte, fyo-yo time.

Once it's finished, it'll spit out an error report.  Fix the errors, revalidate, then GZIP and upload to sftp.echonest.com:

    gzip output.json

See me (Chris) for the credentials, or contact David Sohn (dsohn@echonest.com) at the EchoNest.
