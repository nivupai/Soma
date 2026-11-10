# Local protocol sealing

`seal(Protocol)` validates required scientific fields, requirement bindings and
finite canonical JSON, then hashes the document and validation receipt. Receipts
identify schema/validator/producer and explicitly deny verified external
preregistration. Optional registration references remain unverified.

Frozen dataclasses retain immutable canonical bytes; mapping access returns copies.
`write_seal` uses exclusive creation, private file permissions, flush and fsync.
Existing destinations are never overwritten. Read validation recomputes protocol,
scientific and seal hashes. Keep the original fingerprint independently if integrity
against replacement matters: an attacker can replace a local file and recompute its
hash. A seal provides no signature, trusted timestamp, authorship or proof that the
protocol preceded outcome inspection. There is no registration-service adapter.

```sh
soma protocol example source reports/source-protocol.json
soma protocol validate reports/source-protocol.json
soma protocol seal reports/source-protocol.json reports/source-seal.json
```

Do not put participant information, private paths or credentials into protocol
metadata. Redacted exports are convenience filters, not general deidentification.
