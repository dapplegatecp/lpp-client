import os
import json
from bottle import Bottle, run, request, template, response
from csclient import CSClient
from logger_config import logger
from gevent import monkey; monkey.patch_all()
from gevent import sleep

app = Bottle()
cs = CSClient("lpp-client", logger=logger)

def get_appdata(key):
    env_key = key.upper().replace('.', '_').replace('-', '_')
    env_value = os.environ.get(env_key)
    if env_value:
        return env_value
    if cs.ON_DEVICE:
        return cs.get_appdata(key)
    else:
        if os.path.exists("config.json"):
            with open("config.json") as f:
                config = json.load(f)
                value = config.get(key)
                logger.info(f"Getting {key}={value}")
                return value

def set_appdata(key, value):
    logger.info(f"Setting {key}={value}")
    if cs.ON_DEVICE:
        cs.set_appdata(key, value)
    else:
        if os.path.exists("config.json"):
            with open("config.json") as f:
                config = json.load(f)
        else:
            config = {}
        config[key] = value
        with open("config.json", "w") as f:
            json.dump(config, f)

@app.route('/')
def index():
    config = {
        'host': get_appdata("lpp-client.host") or "129.192.82.125",
        'port': get_appdata("lpp-client.port") or 5431,
        'serial': get_appdata("lpp-client.serial") or "/dev/ttyS1",
        'baud': get_appdata("lpp-client.baud") or 115200,
        'output': get_appdata("lpp-client.output") or "un",
        'format': get_appdata("lpp-client.format") or "osr",
        'forwarding': get_appdata("lpp-client.forwarding") or "",
        'flags': get_appdata("lpp-client.flags") or "",
        'path': get_appdata("lpp-client.path") or "/status/rtk/nmea",
        'starting_mcc': get_appdata("lpp-client.starting_mcc") or "",
        'starting_mnc': get_appdata("lpp-client.starting_mnc") or "",
        'starting_tac': get_appdata("lpp-client.starting_tac") or "",
        'starting_cell_id': get_appdata("lpp-client.starting_cell_id") or "",
        'mcc': get_appdata("lpp-client.mcc") or "",
        'mnc': get_appdata("lpp-client.mnc") or "",
        'tac': get_appdata("lpp-client.tac") or "",
        'cell_id': get_appdata("lpp-client.cell_id") or "",
        'imsi': get_appdata("lpp-client.imsi") or ""
    }
    return template('config_form.tpl', config=config)

@app.route('/logs')
def stream_logs():
    response.content_type = 'text/event-stream'
    response.cache_control = 'no-cache'
    response.connection = 'keep-alive'
    
    def generate():
        last_pos = 0
        heartbeat_counter = 0
        yield "event: heartbeat\ndata: ping\n\n"
        try:
            with open("/log/main.txt") as log_file:
                while True:
                    log_file.seek(last_pos)
                    new_content = log_file.read()
                    if new_content:
                        for line in new_content.splitlines():
                            if line.strip():
                                yield f"data: {line}\n\n"
                        last_pos = log_file.tell()
                    
                    heartbeat_counter += 1
                    if heartbeat_counter >= 30:
                        yield "event: heartbeat\ndata: ping\n\n"
                        heartbeat_counter = 0
                    
                    sleep(0.5)
                
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    return generate()

@app.route('/send_log', method='POST')
def send_log():
    msg = request.forms.get('msg')
    logger.info(msg)
    logger.warning(msg)
    logger.error(msg)
    logger.debug(msg)

@app.route('/update', method='POST')
def update_config():
    for key in request.forms:
        set_appdata(f"lpp-client.{key}", request.forms.get(key))
    response.status = 303
    response.set_header('Location', '/')
    return "Redirecting..."

if __name__ == '__main__':
    if os.environ.get('WEBAPP', False).lower() in ['true', 'yes', '1', 1, True]:
        logger.info("Starting webapp on port 8080...")
        run(app, host='0.0.0.0', port=8080, server='gevent')
        exit(1)
    exit(0)