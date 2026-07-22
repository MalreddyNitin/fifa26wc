# Data sources and limitations

- SofaScore is an unofficial upstream source whose schema and availability can
  change. Raw payloads and hashes are retained for audit.
- Advanced statistics are sparse historically and missingness is not converted
  to zero.
- Source-displayed rankings are not a substitute for a point-in-time official
  FIFA ranking feed.
- The historical corpus contains matches involving at least one of the 48
  registered teams; it is not every international match ever played.
- The simulator models goals from team strength and uses a deterministic
  fallback after sport tiebreakers the model can represent. It does not
  simulate disciplinary fair-play points.
- No bookmaker odds are fabricated. EV reports require timestamped pre-kickoff
  prices imported through the documented schema.
- Predictions are probabilistic research outputs, not financial advice.
