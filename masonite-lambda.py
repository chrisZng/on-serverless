from wsgi import application
import sys
import base64
from io import BytesIO
from urllib.parse import urlencode

def lambda_handler(event, context):
    headers = event.get('headers', {})

    if event['headers'].get('X-Forwarded-Proto'):
        scheme = event['headers']['X-Forwarded-Proto']
    elif event['headers'].get('CloudFront-Forwarded-Proto'):
        scheme = event['headers']['CloudFront-Forwarded-Proto']
    else:
        scheme = 'https'

    if scheme == 'http':
        port = '80'
    else:
        port = '443'

    environ = {
        'REQUEST_METHOD': event['httpMethod'],
        'PATH_INFO': event['path'],
        'QUERY_STRING': urlencode(event.get('queryStringParameters', '') or ''),
        # 'CONTENT_TYPE': '',
        # 'CONTENT_LENGTH': '',
        'SERVER_NAME': event['requestContext']['domainName'],
        'SERVER_PORT': port,
        'SERVER_PROTOCOL': event['requestContext']['protocol'],
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': scheme,
        'wsgi.input': BytesIO((event.get('body') or '').encode('utf-8')),
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
    }

    for header, value in headers.items():
        header_key = 'HTTP_' + header.upper().replace('-', '_')
        environ[header_key] = value

    response_data = {'status': None, 'headers': None}

    def start_response(status, response_headers, exc_info=None):
        if exc_info:
            try:
                if response_data['status'] is not None:
                    raise exc_info[1].with_traceback(exc_info[2])
            finally:
                exc_info = None
        response_data['status'] = status
        response_data['headers'] = response_headers
        return lambda body: None

    try:
        response_iter = application(environ, start_response)
        response_body = b''.join(response_iter)
        if response_data['status'] is None:
            raise RuntimeError('start_response() was not called')

        status_code = int(response_data['status'].split(' ')[0])
        headers = dict(response_data['headers'])

        is_base64_encoded = False
        content_type = headers.get('Content-Type', 'application/octet-stream')
        is_text = content_type.startswith('text/') or content_type in ['application/json', 'application/xml']

        if not is_text and response_body:
            response_body = base64.b64encode(response_body).decode('utf-8')
            is_base64_encoded = True

        return {
            'statusCode': status_code,
            'headers': headers,
            'body': response_body,
            'isBase64Encoded': is_base64_encoded 
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': 'Internal Server Error'
        }
