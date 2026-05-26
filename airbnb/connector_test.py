import os
import sys
import traceback

print('--- Snowflake connector test starting ---')

# Show relevant env vars (masked)
def mask(v):
    if not v:
        return '<MISSING>'
    s = str(v)
    if len(s) > 8:
        return s[:4] + '...' + s[-4:]
    return s

keys = ['SNOWFLAKE_ACCOUNT','DBT_USER','PRIVATE_KEY','PRIVATE_KEY_PASSPHRASE','SSL_CERT_PATH','HTTP_PROXY','HTTPS_PROXY']
for k in keys:
    v = os.environ.get(k)
    print(f'{k}:', mask(v))

account = os.environ.get('SNOWFLAKE_ACCOUNT')
user = os.environ.get('DBT_USER')
priv = os.environ.get('PRIVATE_KEY')
passphrase = os.environ.get('PRIVATE_KEY_PASSPHRASE')
ssl_cert = os.environ.get('SSL_CERT_PATH') or os.environ.get('ssl_cert_path')

if not account or not user or not priv:
    print('\nMissing required environment variables. Ensure you dot-source set-env.ps1 in the same shell before running this test.')
    sys.exit(2)

# Prepare private key: detect if it's a file path or PEM content
import os.path
priv_bytes = None
if os.path.exists(priv):
    print('\nPRIVATE_KEY looks like a file path; reading file...')
    with open(priv, 'rb') as f:
        priv_bytes = f.read()
else:
    print('\nPRIVATE_KEY appears to be inline PEM (or base64).')
    priv_str = priv
    # If looks like base64, decode
    if '\n' not in priv_str and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\r\n' for c in priv_str.strip()):
        try:
            import base64
            priv_bytes = base64.b64decode(priv_str)
        except Exception:
            priv_bytes = priv_str.encode('utf-8')
    else:
        priv_bytes = priv_str.encode('utf-8')

# Use cryptography to load key
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
except Exception:
    print('\ncryptography package is not available in the environment')
    traceback.print_exc()
    sys.exit(3)

# Try multiple parsing strategies: PEM, DER, then wrap base64 as PEM
key = None
errors = []
try:
    key = serialization.load_pem_private_key(priv_bytes, password=passphrase.encode() if passphrase else None, backend=default_backend())
except Exception as e:
    errors.append(('PEM', repr(e)))
    try:
        key = serialization.load_der_private_key(priv_bytes, password=passphrase.encode() if passphrase else None, backend=default_backend())
    except Exception as e2:
        errors.append(('DER', repr(e2)))
        try:
            import base64
            b64 = base64.b64encode(priv_bytes).decode('ascii')
            pem = '-----BEGIN PRIVATE KEY-----\n'
            for i in range(0, len(b64), 64):
                pem += b64[i:i+64] + '\n'
            pem += '-----END PRIVATE KEY-----\n'
            key = serialization.load_pem_private_key(pem.encode('utf-8'), password=passphrase.encode() if passphrase else None, backend=default_backend())
        except Exception as e3:
            errors.append(('Wrapped-PEM', repr(e3)))

if not key:
    print('\nFailed to parse private key via multiple methods; errors:')
    for t, e in errors:
        print(t + ':', e)
    print('\nPrivate key sample (first 800 bytes):')
    try:
        print(priv_bytes[:800])
    except Exception:
        print('<could not print raw bytes>')
    sys.exit(3)

private_key_bytes = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Try connecting
try:
    import snowflake.connector
    print('\nAttempting connection (this may timeout)...')
    conn = snowflake.connector.connect(
        account=account,
        user=user,
        private_key=private_key_bytes,
        ocsp_fail_open=False,
        client_session_keep_alive=False,
        insecure_mode=False,
        application='connector-test'
    )
    cur = conn.cursor()
    cur.execute('select current_version()')
    row = cur.fetchone()
    print('\nConnected. Snowflake version:', row)
    cur.close()
    conn.close()
    print('\n--- Connector test completed: SUCCESS ---')
except Exception as e:
    print('\n--- Connector test FAILED with exception ---')
    traceback.print_exc()
    try:
        import snowflake.connector
        print('\nConnector module version:', getattr(snowflake.connector, '__version__', '<unknown>'))
    except Exception:
        pass
    sys.exit(4)
