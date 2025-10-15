# Messaging System API Documentation

## Overview

The Messaging System API provides real-time messaging capabilities with enterprise-grade security, performance, and reliability features. This documentation covers all endpoints, security measures, and implementation details.

## Table of Contents

1. [Authentication](#authentication)
2. [Security Features](#security-features)
3. [REST API Endpoints](#rest-api-endpoints)
4. [WebSocket API](#websocket-api)
5. [File Upload Security](#file-upload-security)
6. [Rate Limiting](#rate-limiting)
7. [Error Handling](#error-handling)
8. [Performance Features](#performance-features)
9. [Monitoring & Analytics](#monitoring--analytics)

---

## Authentication

### JWT Authentication
All API endpoints require JWT authentication via the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

### Session Authentication (WebSocket)
WebSocket connections use session-based authentication:
1. Client makes a GET request to `/api/csrf/` to establish session
2. WebSocket connection uses session cookies for authentication
3. Fallback to JWT token in URL if session unavailable

---

## Security Features

### Content Sanitization
All user-generated content is automatically sanitized to prevent XSS attacks:

- **Message Content**: HTML tags are stripped, dangerous characters removed
- **File Names**: Path traversal attempts blocked, special characters sanitized
- **Message Types**: Only predefined types allowed (`text`, `image`, `file`, `system`)

### File Upload Security
Comprehensive file validation and security measures:

- **MIME Type Validation**: Files must match their declared content type
- **File Size Limits**: 
  - Images: 10MB max
  - Videos/Audio: 50MB max
  - Documents: 25MB max
- **File Extension Validation**: Extensions must match MIME type
- **Malicious File Detection**: Executable files and scripts blocked
- **Content Validation**: File content verified against declared type

### Rate Limiting
Multi-level rate limiting to prevent abuse:

- **Message Rate Limiting**: 60 messages per minute per user
- **Connection Rate Limiting**: 10 connections per minute per user
- **Typing Rate Limiting**: 30 typing events per minute per user
- **IP-based Limiting**: Additional limits per IP address

---

## REST API Endpoints

### Base URL
```
https://your-domain.com/api/messaging/
```

### Conversations

#### List Conversations
```http
GET /conversations/
Authorization: Bearer <jwt_token>
```

**Response:**
```json
[
  {
    "conversation_id": 1,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "participants": [1, 2],
    "last_message": {
      "message_id": 1,
      "content": "Hello!",
      "sender_id": 1,
      "created_at": "2024-01-01T00:00:00Z"
    }
  }
]
```

#### Create Conversation
```http
POST /conversations/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "participant_ids": [2, 3]
}
```

### Messages

#### List Messages
```http
GET /conversations/{conversation_id}/messages/
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
- `cursor`: Pagination cursor (optional)
- `limit`: Number of messages to return (default: 50, max: 100)

**Response:**
```json
{
  "results": [
    {
      "message_id": 1,
      "content": "Hello!",
      "sender_id": 1,
      "sender_name": "John Doe",
      "message_type": "text",
      "created_at": "2024-01-01T00:00:00Z",
      "is_read": false,
      "attachments": []
    }
  ],
  "next_cursor": "eyJ0aW1lc3RhbXAiOjE3MDQ2NzIwMDB9",
  "has_more": true
}
```

#### Send Message
```http
POST /conversations/{conversation_id}/messages/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "content": "Hello, world!",
  "message_type": "text",
  "attachment_id": 123
}
```

**Response:**
```json
{
  "message_id": 1,
  "content": "Hello, world!",
  "sender_id": 1,
  "sender_name": "John Doe",
  "message_type": "text",
  "created_at": "2024-01-01T00:00:00Z",
  "is_read": false,
  "attachments": []
}
```

### File Attachments

#### Upload Attachment
```http
POST /conversations/{conversation_id}/attachments/
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

file: <binary_file_data>
```

**Response:**
```json
{
  "attachment_id": 123,
  "file_name": "document.pdf",
  "file_type": "application/pdf",
  "file_category": "document",
  "file_size": 1024000,
  "file_url": "https://s3.amazonaws.com/bucket/file.pdf",
  "uploaded_at": "2024-01-01T00:00:00Z"
}
```

**Security Validations:**
- File size limits enforced
- MIME type validation
- File extension validation
- Malicious content detection
- Filename sanitization

### Statistics

#### Get Messaging Statistics
```http
GET /stats/
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "total_conversations": 10,
  "total_messages": 150,
  "total_unread": 5,
  "recent_activity": [
    {
      "conversation_id": 1,
      "last_message_at": "2024-01-01T00:00:00Z",
      "unread_count": 2
    }
  ]
}
```

---

## WebSocket API

### Connection
```javascript
// Establish session first
await fetch('/api/csrf/');

// Connect to WebSocket
const ws = new WebSocket('ws://your-domain.com/ws/chat/{conversation_id}/');
```

### Message Types

#### Send Message
```json
{
  "type": "message",
  "message": "Hello, world!",
  "message_type": "text"
}
```

#### Typing Indicator
```json
{
  "type": "typing",
  "is_typing": true
}
```

### Received Messages

#### Chat Message
```json
{
  "type": "chat_message",
  "message_id": 1,
  "sequence_number": 1,
  "content": "Hello, world!",
  "sender_id": 1,
  "sender_name": "John Doe",
  "message_type": "text",
  "created_at": "2024-01-01T00:00:00Z",
  "timestamp": "2024-01-01T00:00:00Z",
  "microsecond_timestamp": 1704672000000
}
```

#### Typing Indicator
```json
{
  "type": "user_typing",
  "user_id": 1,
  "user_name": "John Doe",
  "is_typing": true,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Connection Status
```json
{
  "type": "connection_established",
  "conversation_id": 1,
  "user_id": 1,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Rate Limit Exceeded
```json
{
  "type": "rate_limit_exceeded",
  "reason": "message_rate_limit_exceeded",
  "retry_after": 60,
  "message": "Message rate limit exceeded. Please slow down."
}
```

---

## File Upload Security

### Supported File Types

#### Images
- JPEG, PNG, GIF, WebP, BMP, TIFF
- Maximum size: 10MB
- Content validation: Image headers verified

#### Documents
- PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX
- TXT, CSV, RTF
- OpenDocument formats (ODT, ODS, ODP)
- Maximum size: 25MB

#### Media Files
- Audio: MP3, WAV, M4A, OGG
- Video: MP4, AVI, MOV
- Maximum size: 50MB

#### Archives
- ZIP, RAR, 7Z
- Maximum size: 25MB

### Security Measures

1. **MIME Type Validation**: File content must match declared MIME type
2. **File Extension Validation**: Extension must match MIME type
3. **Content Validation**: File headers verified against declared type
4. **Size Limits**: Enforced based on file category
5. **Filename Sanitization**: Path traversal and special characters removed
6. **Malicious File Detection**: Executable files and scripts blocked

---

## Rate Limiting

### Limits

| Operation | Limit | Window | Scope |
|-----------|-------|--------|-------|
| Messages | 60 | 1 minute | Per user |
| Connections | 10 | 1 minute | Per user |
| Typing | 30 | 1 minute | Per user |
| File Uploads | 20 | 1 minute | Per user |
| IP Connections | 100 | 1 minute | Per IP |

### Rate Limit Headers
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1704672060
```

### Rate Limit Responses
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60,
  "limit": 60,
  "remaining": 0
}
```

---

## Error Handling

### Standard Error Response
```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

### Common Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `AUTHENTICATION_REQUIRED` | JWT token missing or invalid | 401 |
| `PERMISSION_DENIED` | User lacks required permissions | 403 |
| `CONVERSATION_NOT_FOUND` | Conversation does not exist | 404 |
| `MESSAGE_NOT_FOUND` | Message does not exist | 404 |
| `RATE_LIMIT_EXCEEDED` | Rate limit exceeded | 429 |
| `FILE_TOO_LARGE` | File exceeds size limit | 400 |
| `INVALID_FILE_TYPE` | File type not allowed | 400 |
| `CONTENT_TOO_LONG` | Message content too long | 400 |
| `INVALID_MESSAGE_TYPE` | Invalid message type | 400 |

### WebSocket Error Handling
```json
{
  "type": "error",
  "message": "Error description",
  "code": "ERROR_CODE"
}
```

---

## Performance Features

### Caching
- **Message Caching**: Recent messages cached in Redis
- **Conversation Caching**: User conversation lists cached
- **Metadata Caching**: Conversation metadata cached

### Database Optimization
- **Query Optimization**: N+1 queries eliminated with select_related/prefetch_related
- **Indexing**: Optimized database indexes for common queries
- **Pagination**: Cursor-based pagination for large datasets

### Message Ordering
- **Sequence Numbers**: Messages assigned sequence numbers for proper ordering
- **Race Condition Handling**: REST/WebSocket race conditions resolved
- **Deduplication**: Duplicate messages automatically removed

---

## Monitoring & Analytics

### Performance Metrics
- Message delivery latency
- WebSocket connection times
- Database query performance
- Cache hit ratios

### Error Tracking
- Sentry integration for error monitoring
- Custom error metrics and alerting
- Performance bottleneck detection

### Analytics Endpoints

#### Get Performance Metrics
```http
GET /admin/performance-metrics/
Authorization: Bearer <admin_jwt_token>
```

#### Get System Health
```http
GET /admin/health-check/
Authorization: Bearer <admin_jwt_token>
```

### Management Commands
```bash
# Run comprehensive tests
python manage.py run_messaging_tests --verbose --report

# Check system health
python manage.py messaging_monitoring --health-check

# View performance metrics
python manage.py performance_metrics --summary

# Monitor WebSocket connections
python manage.py websocket_analytics
```

---

## Security Best Practices

### Client-Side Security
1. **Input Validation**: Validate all user inputs client-side
2. **Content Sanitization**: Sanitize content before sending
3. **Error Handling**: Don't expose sensitive information in errors
4. **Session Management**: Properly handle session cookies

### Server-Side Security
1. **Authentication**: Always verify JWT tokens
2. **Authorization**: Check user permissions for each operation
3. **Input Validation**: Validate and sanitize all inputs
4. **Rate Limiting**: Enforce rate limits to prevent abuse
5. **File Security**: Comprehensive file validation and sanitization

### Production Deployment
1. **HTTPS Only**: Use HTTPS for all communications
2. **CORS Configuration**: Properly configure CORS policies
3. **Environment Variables**: Use environment variables for sensitive data
4. **Logging**: Implement comprehensive logging without exposing secrets
5. **Monitoring**: Set up error tracking and performance monitoring

---

## Support & Maintenance

### Testing
Run the comprehensive test suite:
```bash
python manage.py run_messaging_tests --verbose --report --coverage
```

### Monitoring
Monitor system health and performance:
```bash
python manage.py messaging_monitoring --status
python manage.py performance_metrics --trends message_delivery
```

### Troubleshooting
Common issues and solutions:

1. **WebSocket Connection Issues**: Check session authentication and CORS settings
2. **File Upload Failures**: Verify file size, type, and content validation
3. **Rate Limit Exceeded**: Implement exponential backoff in client
4. **Performance Issues**: Check database queries and cache hit ratios

---

## Version History

- **v1.0.0**: Initial implementation
- **v1.1.0**: Added security features and content sanitization
- **v1.2.0**: Implemented Redis caching and performance optimizations
- **v1.3.0**: Added cloud storage and comprehensive monitoring
- **v1.4.0**: Enhanced testing suite and documentation

---

## Contact & Support

For technical support or questions about the Messaging System API:

- **Documentation**: This file and inline code comments
- **Testing**: Run `python manage.py run_messaging_tests` for comprehensive testing
- **Monitoring**: Use management commands for system health and performance monitoring
- **Issues**: Check logs and monitoring dashboards for error details


