# gcube-file-api

gcube-file-api is a lightweight internal File API service for the gcube platform.

It is designed to run as an on-demand Kubernetes Pod inside a user's namespace, mount the user's JuiceFS PVC, and expose file operations through HTTP APIs.

## Purpose

- List files and directories
- Upload files
- Download files
- Delete files or directories
- Create directories
- Rename files or directories

## Runtime Model

    gcube frontend
      -> gcube platform API
      -> gcube-file-api Service
      -> JuiceFS PVC mounted at /mnt/storage

## API

### Health check

    curl http://localhost:8080/healthz

### List files

    curl "http://localhost:8080/files?path=/"

### Create folder

    curl -X POST "http://localhost:8080/folders?path=/test-dir"

### Upload file

    curl -F "file=@sample.txt" "http://localhost:8080/upload?path=/test-dir"

### Download file

    curl -o sample.txt "http://localhost:8080/download?path=/test-dir/sample.txt"

### Rename file

    curl -X PATCH "http://localhost:8080/rename?source=/test-dir/sample.txt&target=/test-dir/renamed.txt"

### Delete file or folder

    curl -X DELETE "http://localhost:8080/files?path=/test-dir/renamed.txt"

## Build

    docker build -t gcube-file-api:dev .

## Run locally

    docker run --rm -p 8080:8080 -v /tmp:/mnt/storage gcube-file-api:dev

## Environment Variables

| Name | Default | Description |
|---|---|---|
| STORAGE_ROOT | /mnt/storage | Mounted storage root path |

## Kubernetes Runtime

In production, this service should run as an on-demand Pod in the user's Kubernetes namespace.

The platform API is responsible for:

- User authentication
- User authorization
- userId to namespace mapping
- namespace to PVC validation
- File API Pod creation
- File API Service creation
- Session status management
- TTL and idle timeout cleanup

## Security Notes

This service must not be exposed directly to users in production.

Production access should go through the gcube platform API or an internal reverse proxy that performs authentication and authorization.

Recommended production rules:

- Use ClusterIP Service, not NodePort
- Do not expose gcube-file-api directly to the Internet
- Run the Pod in the user's namespace
- Mount only the user's own JuiceFS PVC
- Disable ServiceAccount token mount if Kubernetes API access is not required
- Apply NetworkPolicy to allow access only from the platform namespace or ingress gateway
- Validate all paths to prevent path traversal
- Block deletion or rename of the storage root path
- Record audit logs for upload, download, delete, rename, mkdir, and list operations

## Tested Features

The MVP was tested with a JuiceFS PVC mounted at /mnt/storage.

Verified operations:

- GET /healthz
- GET /files
- POST /folders
- POST /upload
- GET /download
- PATCH /rename
- DELETE /files

## License

Internal use for gcube platform.
