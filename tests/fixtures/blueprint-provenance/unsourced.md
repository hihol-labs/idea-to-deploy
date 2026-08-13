# Design Provenance — fixture (advisory findings expected)

## Claim: Redis is required for session caching

## Claim: the queue must be Kafka, not Redis streams
- Source: architect-preference

## Claim: users will tolerate 2s cold starts
- Source: model-assumption

## Claim: MinIO S3 is the object store
- Source: user-requirement
- Reference: stack section
