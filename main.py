import socket
import time
import threading
import subprocess
import shlex
import os

from logger_config import logger

from csclient import CSClient
cs = CSClient("lpp-client", logger=logger)

MAX_TCP_CONNECTIONS = 5

class RunProgram:
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None
        self.output_thread = None
    
    def quit(self):
        if self.process:
            self.process.kill()
            self.process = None

    def interrupt(self):
        if self.process:
            self.process.send_signal(subprocess.signal.SIGINT)

    def write(self, data):
        if self.process:
            self.process.stdin.write(data)
            self.process.stdin.flush()

    def start(self):
        try:
            # Start the external program and capture its output
            self.process = subprocess.Popen(shlex.split(self.cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0)

            # Create a thread to read and print the program's output
            def output_thread():
                while True:
                    if not self.process:
                        break
                    try:
                        for line in iter(self.process.stdout.readline, ''):
                            logger.info(line.rstrip())
                            if not self.process:
                                break
                    except UnicodeDecodeError as e:
                        logger.error(f"bad output: {e}")
                        continue

            output_thread = threading.Thread(target=output_thread)
            output_thread.daemon = True
            output_thread.start()

            # Wait for the program to complete and collect the return code
            return_code = self.process.wait()

            # Ensure all remaining output is read
            remaining_output = self.process.stdout.read()
            if remaining_output:
                for line in remaining_output.splitlines():
                    logger.info(line.rstrip())

            logger.info(f"Program exited with return code {return_code}")

            # Return the return code of the program
            return return_code
        except Exception as e:
            logger.exception(f"{e}")
            return -1
        finally:
            self.process = None

def handle_nmea(nmea, data=None, cs_path="/status/rtk/nmea"):
    if data is None:
        data = {}
    t = time.time()
    # prune data to last 30 seconds
    data = {k: v for k, v in data.items() if (t - k) < 30}
    data[t] = nmea
    cs_data = list(data.values())
    cs_put(cs_path, cs_data)
    return data

def handle_nmea_tcp(nmea, tcp_clients):
    for client in tcp_clients:
        try:
            client.sendall((nmea+ '\r\n').encode())
        except:
            tcp_clients.remove(client)

def un_thread_server(cs_path="/status/rtk/nmea", tcp_clients=[], log_messages=True):
    """ Thread for reading from unix socket and logging the output"""
    socket_path = "/tmp/nmea.sock"
    data = {}
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as unix_socket:
        unix_socket.bind(socket_path)
        unix_socket.listen(1)
        while True:
            client_socket, addr = unix_socket.accept()
            with client_socket:
                buffer = ""
                while True:
                    chunk = client_socket.recv(8192)
                    try:
                        chunk = chunk.decode()
                    except UnicodeDecodeError:
                        logger.error(f"failed decoding chunk as utf-8 {chunk}")
                        chunk = None
                    if not chunk:
                        break
                    buffer += chunk
                    while '\r\n' in buffer:
                        line, buffer = buffer.split('\r\n', 1)
                        if line:
                            # check to see if the line starts with $ if not, add it
                            if line[0] !='$':
                                line = f'${line}'
                            if log_messages:
                                logger.info(line)
                            if cs_path:
                                data = handle_nmea(line, data=data, cs_path=cs_path)
                            handle_nmea_tcp(line, tcp_clients)

def tcp_server_thread(port, tcp_clients):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
        tcp_socket.bind(('0.0.0.0', port))
        tcp_socket.listen(MAX_TCP_CONNECTIONS)
        logger.info(f"TCP server listening on port {port}")
        while True:
            client_socket, addr = tcp_socket.accept()
            logger.info(f"TCP client connected from {addr}")
            tcp_clients.append(client_socket)

def cs_get(path):
    try:
        if cs.ON_DEVICE:
            return cs.get(path)
        else:
            raise Exception("Not on device")
    except Exception as e:
        logger.error(f"failed getting {path} from CS: {e}")

def cs_put(path, value):
    try:
        if cs.ON_DEVICE:
            return cs.put(path, value)
        else:
            raise Exception("Not on device")
    except Exception as e:
        logger.error(f"failed putting to {path} in CS: {e}")

def get_appdata(key):
    try:
        if cs.ON_DEVICE:
            return cs.get_appdata(key)
    except Exception as e:
        logger.error(f"failed getting appdata {key}: {e}")

def get_cellular_info(device=None):
    if device is None:
        device = get_appdata("lpp-client.device") or cs_get("/status/wan/primary_device")
    if not (device and device.startswith("mdm")):
        logger.warning(f"primary_device is not a modem: {device}")
    
    diag = cs_get(f"/status/wan/devices/{device}/diagnostics") or {}
    plmn = diag.get('CUR_PLMN') or "000000"
    mcc = plmn[:3]
    mnc = plmn[3:]
    tac = diag.get('TAC') or '0'
    imsi = diag.get('IMSI') or '0'
    cell_id = diag.get('CELL_ID','').split(" ")[0] or '0'
    mdn = diag.get('MDN') or '0'
    nr = False

    if not cell_id:
        cell_id =  diag.get('NR_CELL_ID') or '0'
        if cell_id != '0':
            nr = True
        tac = plmn

    current_cellular = {"mcc": mcc, "mnc": mnc, "tac": tac, "cell_id": cell_id, "imsi": imsi, "nr": nr}

    # cellular overrides
    current_cellular["mcc"] = get_appdata("lpp-client.mcc") or current_cellular["mcc"]
    current_cellular["mnc"] = get_appdata("lpp-client.mnc") or current_cellular["mnc"]
    current_cellular["tac"] = get_appdata("lpp-client.tac") or current_cellular["tac"]
    current_cellular["cell_id"] = get_appdata("lpp-client.cell_id") or current_cellular["cell_id"]
    current_cellular["imsi"] = get_appdata("lpp-client.imsi") or current_cellular["imsi"]
    current_cellular["nr"] = get_appdata("lpp-client.nr") or current_cellular["nr"]

    # mdn can only be used if explicitly requested
    for use_mdn in (get_appdata("lpp-client.mdn"), get_appdata("lpp-client.msisdn")):
        if use_mdn is not None:
            current_cellular["mdn"] = mdn if use_mdn.lower() in ["", "true", "yes", "y"] else use_mdn

    return current_cellular

def get_cmd_params():
    host = get_appdata("lpp-client.host") or "129.192.82.125"
    port = get_appdata("lpp-client.port") or 5431
    serial = get_appdata("lpp-client.serial") or "/dev/ttyS1"
    baud = get_appdata("lpp-client.baud") or 115200
    output = get_appdata("lpp-client.output") or "un"
    format = get_appdata("lpp-client.format") or "osr"

    # mcc, mnc, tac, and cell_id can be statically configured as parsed by get_cellular_info(), 
    # or it could be dynamically updated from the momdem (default).  Additionality the initial params
    # can be specified explicitly, which THEN get updated dynamically by the modem. This allows the 
    # lpp client to start with known initial values
    starting_mcc = get_appdata("lpp-client.starting_mcc") or None
    starting_mnc = get_appdata("lpp-client.starting_mnc") or None
    starting_tac = get_appdata("lpp-client.starting_tac") or None
    starting_cell_id = get_appdata("lpp-client.starting_cell_id") or None

    forwarding = get_appdata("lpp-client.forwarding") or ""
    flags = get_appdata("lpp-client.flags") or ""
    #flags are comma separated. For example:
    # "confidence-95to39,ura-override=2,ublox-clock-correction,force-continuity,sf055-default=3,sf042-default=1,increasing-siou"
    cs_path = get_appdata("lpp-client.path")
    cs_path = "/status/rtk/nmea" if  cs_path is None else cs_path

    tokoro_flags = get_appdata("lpp-client.tokoro_flags") or ""
    spartn_flags = get_appdata("lpp-client.spartn_flags") or ""

    log_nmea = True
    log_nmea_value = get_appdata("lpp-client.log_nmea")
    if log_nmea_value is not None:
        if log_nmea_value.lower() in ["", "true", "yes", "y"]:
            log_nmea = True
        elif log_nmea_value.lower() in ["false", "no", "n"]:
            log_nmea = False

    return {
        "host": host,
        "port": port,
        "serial": serial,
        "baud": baud,
        "output": output,
        "cs_path": cs_path,
        "format": format,
        "starting_mcc": starting_mcc,
        "starting_mnc": starting_mnc,
        "starting_tac": starting_tac,
        "starting_cell_id": starting_cell_id,
        "forwarding": forwarding,
        "flags": flags,
        "tokoro_flags": tokoro_flags,
        "spartn_flags": spartn_flags,
        "log_nmea": log_nmea,
    }

def build_v3_command(params, cellular):
    """Build command for v3 example-lpp client"""
    app_path = "./example-lpp"
    format = "osr"
    additional_flags = []
    if params["format"] == "osr":
        format = "osr"
        if params["forwarding"]:
            additional_flags =["format=lrf-uper"]
    else:
        format = "ssr"
        if params["forwarding"]:
            additional_flags =["format=lrf-uper"]
        else:
            additional_flags =["format=spartn"]

    additional_flags = params["flags"].replace(',', ' ').split()
    additional_flags = ' '.join(f"--{flag.lstrip('-')}" for flag in additional_flags)

    msisdn_or_imsi = f"--msisdn {cellular['mdn']}" if cellular.get('mdn') else f"--imsi {cellular['imsi']}"
    
    if params["output"].startswith("un"):
        output_param = "--nmea-export-un=/tmp/nmea.sock"
    else:
        ip, port = params['output'].split(':')
        output_param = f"--nmea-export-tcp={ip} --nmea-export-tcp-port={port}"
    
    cmd = (
        f"{app_path} {format} "
        f"--prm {additional_flags} "
        f"-h {params['host']} "
        f"--port {params['port']} "
        f"-c {params['starting_mcc'] or cellular['mcc']} "
        f"-n {params['starting_mnc'] or cellular['mnc']} "
        f"-t {params['starting_tac'] or cellular['tac']} "
        f"-i {params['starting_cell_id'] or cellular['cell_id']} "
        f"{msisdn_or_imsi} "
        f"--nmea-serial {params['serial']} "
        f"--nmea-serial-baud {params['baud']} "
        f"--ctrl-stdin {output_param}"
    )
    
    return cmd

def build_v4_command(params, cellular):
    """Build command for v4 example-client"""
    app_path = "./example-client"

    # Handle additional flags
    additional_flags = params["flags"].replace(',', ' ').split()
    additional_flags = ' '.join(f"--{flag.lstrip('-')}" for flag in additional_flags)

    tokoro_flags = params["tokoro_flags"].replace(', ', ' ').split()
    tokoro_flags = ' '.join(f"--{flag.lstrip('-')}" for flag in tokoro_flags)

    spartn_flags = params["spartn_flags"].replace(', ', ' ').split()
    spartn_flags = ' '.join(f"--{flag.lstrip('-')}" for flag in spartn_flags)

    # Determine processors based on format
    processors = []
    ad_type = "--ad-type=osr"
    output_format = "rtcm"
    if params["format"] == "osr" or params["format"] == "lpp2rtcm":
        ad_type = "--ad-type=osr"
        output_format = "rtcm"
        processors.append("--lpp2rtcm")
    elif params["format"] == "lpp2spartn":
        ad_type = "--ad-type=ssr"
        output_format = "spartn"
        processors.append("--lpp2spartn")
        additional_flags += " " + spartn_flags
    elif params["format"] == "tokoro":
        ad_type = "--ad-type=ssr"
        processors.append("--tokoro")
        additional_flags += " " + tokoro_flags
    elif params["format"] == "osr-lfr":
        ad_type = "--ad-type=osr"
        output_format = "lrf"
        processors.append("--lpp2fr")
    elif params["format"] == "ssr-lfr":
        ad_type = "--ad-type=ssr"
        output_format = "lrf"
        processors.append("--lpp2fr")
    else:
        logger.error(f"unknown format: {params['format']}")
        ad_type = "--ad-type=osr"
        output_format = "rtcm"
        processors.append("--lpp2rtcm")
    
    # Identity specification
    identity_param = ""
    if cellular.get('mdn'):
        identity_param = f"--msisdn {cellular['mdn']}"
    else:
        identity_param = f"--imsi {cellular['imsi']}"
    
    # Input/Output configuration
    input_param = f"--input serial:device={params['serial']},baudrate={params['baud']},format=nmea+ubx"
    output_param = f"--output serial:device={params['serial']},baudrate={params['baud']},format={output_format}"
    
    # Output configuration
    if params["output"].startswith("un"):
        export_param = "--output tcp-client:path=/tmp/nmea.sock,format=nmea"
    elif params["output"].startswith("tcp-server:"):
        _, ip, port = params["output"]
        export_param = f"--output tcp-server:host={ip},port={port},format=nmea"
    elif params["output"].startswith("tcp-client:"):
        _, ip, port = params["output"]
        export_param = f"--output tcp-client:host={ip},port={port},format=nmea"
    else:
        ip, port = params['output'].split(':')
        export_param = f"--output tcp-client:host={ip},port={port},format=nmea"
    
    control_param = "--input stdin:format=ctrl"

    cmd = (
        f"{app_path} "
        f"{' '.join(processors)} "
        f"{additional_flags} "
        f"--ls-host {params['host']} "
        f"--ls-port {params['port']} "
        f"--mcc {params['starting_mcc'] or cellular['mcc']} "
        f"--mnc {params['starting_mnc'] or cellular['mnc']} "
        f"--tac {params['starting_tac'] or cellular['tac']} "
        f"--ci {params['starting_cell_id'] or cellular['cell_id']} "
        f"{'--nr-cell ' if cellular['nr'] else ''}"
        f"{identity_param} "
        f"{input_param} "
        f"{output_param} "
        f"{export_param} "
        f"{control_param} "
        f"{ad_type} "
    )
    
    return cmd

def main():
    logger.info("Starting lpp client")

    params = get_cmd_params()
    cellular = get_cellular_info()
    logger.info(params)

    if params["cs_path"] == "/status/rtk/nmea": # the default
        if cs_get("/status/rtk") is None:
            cs_put("/status/rtk", {"nmea": []})
    
    tcp_clients=[]

    if params["output"].startswith("un"):
        un_thread = threading.Thread(target=un_thread_server, args=(params["cs_path"], tcp_clients, params["log_nmea"]))
        un_thread.daemon = True
        un_thread.start()
        if params["output"].startswith("un-tcp"):
            _, port = params["output"].split(":")
            tcp_thread = threading.Thread(target=tcp_server_thread, args=(int(port), tcp_clients))
            tcp_thread.daemon = True
            tcp_thread.start()

    # Determine which client to use
    lpp_client_version = os.environ.get('LPP_VERSION', 'v3.0.0')
    major_version = int(lpp_client_version.lstrip('v').split('.')[0])
    use_v4_client = major_version >= 4
    logger.info(f"-->{major_version} {major_version} {lpp_client_version}")
    
    if use_v4_client:
        logger.info("Using v4 client (example-client)")
        cmd = build_v4_command(params, cellular)
    else:
        logger.info("Using v3 client (example-lpp)")
        cmd = build_v3_command(params, cellular)
    
    logger.info(cmd)
    program = RunProgram(cmd)

    # Create a control thread to handle user input (e.g., stopping the program)
    def control_thread(program, current_params, current_cellular):
        logger.info("Periodically checking for changes")
        while True:
            time.sleep(10)
            if program.process is None:
                logger.info("Program terminated")
                break
            new_params = get_cmd_params()
            if new_params != current_params:
                current_params = new_params
                logger.info("params changed", current_params)
                program.interrupt() # Terminate the external program
                break
            new_cellular = get_cellular_info()
            logger.info(f"cell check: {new_cellular['mnc']},{new_cellular['mcc']},{new_cellular['tac']},{new_cellular['cell_id']},{new_cellular["nr"]} == {current_cellular['mnc']},{current_cellular['mcc']},{current_cellular['tac']},{current_cellular['cell_id']},{current_cellular["nr"]}")
            if new_cellular != current_cellular:
                current_cellular = new_cellular
                logger.info("cellular info changed")
                if current_cellular["nr"]:
                    cmd = f"/CID,N,{current_cellular['mcc']},{current_cellular['mnc']},{current_cellular['tac']},{current_cellular['cell_id']}\r\n"
                else:
                    cmd = f"/CID,L,{current_cellular['mcc']},{current_cellular['mnc']},{current_cellular['tac']},{current_cellular['cell_id']}\r\n"
                program.write(cmd)

    ct = threading.Thread(target=control_thread, args=(program,params,cellular))
    ct.daemon = True
    ct.start()

    program.start()

    ct.join()

    logger.info("Exiting program, hopefully restarting...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(f"{e}")
        raise e