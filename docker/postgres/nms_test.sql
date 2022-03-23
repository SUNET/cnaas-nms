--
-- PostgreSQL database dump
--

-- Dumped from database version 11.10 (Debian 11.10-1.pgdg90+1)
-- Dumped by pg_dump version 11.10 (Debian 11.10-1.pgdg90+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: devicestate; Type: TYPE; Schema: public; Owner: cnaas
--

CREATE TYPE public.devicestate AS ENUM (
    'UNKNOWN',
    'PRE_CONFIGURED',
    'DHCP_BOOT',
    'DISCOVERED',
    'INIT',
    'MANAGED',
    'MANAGED_NOIF',
    'UNMANAGED'
);


ALTER TYPE public.devicestate OWNER TO cnaas;

--
-- Name: devicetype; Type: TYPE; Schema: public; Owner: cnaas
--

CREATE TYPE public.devicetype AS ENUM (
    'UNKNOWN',
    'ACCESS',
    'DIST',
    'CORE'
);


ALTER TYPE public.devicetype OWNER TO cnaas;

--
-- Name: interfaceconfigtype; Type: TYPE; Schema: public; Owner: cnaas
--

CREATE TYPE public.interfaceconfigtype AS ENUM (
    'UNKNOWN',
    'UNMANAGED',
    'CONFIGFILE',
    'CUSTOM',
    'TEMPLATE',
    'MLAG_PEER',
    'ACCESS_AUTO',
    'ACCESS_UNTAGGED',
    'ACCESS_TAGGED',
    'ACCESS_UPLINK',
    'ACCESS_DOWNLINK'
);


ALTER TYPE public.interfaceconfigtype OWNER TO cnaas;

--
-- Name: jobstatus; Type: TYPE; Schema: public; Owner: cnaas
--

CREATE TYPE public.jobstatus AS ENUM (
    'UNKNOWN',
    'SCHEDULED',
    'RUNNING',
    'FINISHED',
    'EXCEPTION',
    'ABORTED',
    'ABORTING'
);


ALTER TYPE public.jobstatus OWNER TO cnaas;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO cnaas;

--
-- Name: apscheduler_jobs; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.apscheduler_jobs (
    id character varying(191) NOT NULL,
    next_run_time double precision,
    job_state bytea NOT NULL
);


ALTER TABLE public.apscheduler_jobs OWNER TO cnaas;

--
-- Name: device; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.device (
    id integer NOT NULL,
    hostname character varying(64) NOT NULL,
    site_id integer,
    description character varying(255),
    management_ip character varying(50),
    dhcp_ip character varying(50),
    serial character varying(64),
    ztp_mac character varying(12),
    platform character varying(64),
    vendor character varying(64),
    model character varying(64),
    os_version character varying(64),
    synchronized boolean,
    state public.devicestate NOT NULL,
    device_type public.devicetype NOT NULL,
    last_seen timestamp without time zone,
    confhash character varying(64),
    infra_ip character varying(50),
    oob_ip character varying(50),
    port integer
);


ALTER TABLE public.device OWNER TO cnaas;

--
-- Name: device_id_seq; Type: SEQUENCE; Schema: public; Owner: cnaas
--

CREATE SEQUENCE public.device_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.device_id_seq OWNER TO cnaas;

--
-- Name: device_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cnaas
--

ALTER SEQUENCE public.device_id_seq OWNED BY public.device.id;


--
-- Name: interface; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.interface (
    device_id integer NOT NULL,
    name character varying(255) NOT NULL,
    configtype public.interfaceconfigtype NOT NULL,
    data jsonb
);


ALTER TABLE public.interface OWNER TO cnaas;

--
-- Name: job; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.job (
    id integer NOT NULL,
    status public.jobstatus,
    scheduled_time timestamp without time zone,
    start_time timestamp without time zone,
    finish_time timestamp without time zone,
    function_name character varying(255),
    scheduled_by character varying(255),
    comment character varying(255),
    ticket_ref character varying(32),
    next_job_id integer,
    result jsonb,
    exception jsonb,
    finished_devices jsonb,
    change_score smallint,
    start_arguments jsonb
);


ALTER TABLE public.job OWNER TO cnaas;

--
-- Name: job_id_seq; Type: SEQUENCE; Schema: public; Owner: cnaas
--

CREATE SEQUENCE public.job_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.job_id_seq OWNER TO cnaas;

--
-- Name: job_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cnaas
--

ALTER SEQUENCE public.job_id_seq OWNED BY public.job.id;


--
-- Name: joblock; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.joblock (
    name character varying(32) NOT NULL,
    start_time timestamp without time zone,
    abort boolean,
    job_id integer NOT NULL
);


ALTER TABLE public.joblock OWNER TO cnaas;

--
-- Name: linknet; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.linknet (
    id integer NOT NULL,
    ipv4_network character varying(18),
    device_a_id integer,
    device_a_ip character varying(50),
    device_a_port character varying(64),
    device_b_id integer,
    device_b_ip character varying(50),
    device_b_port character varying(64),
    site_id integer,
    description character varying(255)
);


ALTER TABLE public.linknet OWNER TO cnaas;

--
-- Name: linknet_id_seq; Type: SEQUENCE; Schema: public; Owner: cnaas
--

CREATE SEQUENCE public.linknet_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.linknet_id_seq OWNER TO cnaas;

--
-- Name: linknet_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cnaas
--

ALTER SEQUENCE public.linknet_id_seq OWNED BY public.linknet.id;


--
-- Name: mgmtdomain; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.mgmtdomain (
    id integer NOT NULL,
    ipv4_gw character varying(18),
    device_a_id integer,
    device_a_ip character varying(50),
    device_b_id integer,
    device_b_ip character varying(50),
    site_id integer,
    vlan integer,
    description character varying(255),
    esi_mac character varying(12)
);


ALTER TABLE public.mgmtdomain OWNER TO cnaas;

--
-- Name: mgmtdomain_id_seq; Type: SEQUENCE; Schema: public; Owner: cnaas
--

CREATE SEQUENCE public.mgmtdomain_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.mgmtdomain_id_seq OWNER TO cnaas;

--
-- Name: mgmtdomain_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cnaas
--

ALTER SEQUENCE public.mgmtdomain_id_seq OWNED BY public.mgmtdomain.id;


--
-- Name: reservedip; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.reservedip (
    device_id integer NOT NULL,
    ip character varying(50),
    last_seen timestamp without time zone
);


ALTER TABLE public.reservedip OWNER TO cnaas;

--
-- Name: site; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.site (
    id integer NOT NULL,
    description character varying(255)
);


ALTER TABLE public.site OWNER TO cnaas;

--
-- Name: site_id_seq; Type: SEQUENCE; Schema: public; Owner: cnaas
--

CREATE SEQUENCE public.site_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.site_id_seq OWNER TO cnaas;

--
-- Name: site_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cnaas
--

ALTER SEQUENCE public.site_id_seq OWNED BY public.site.id;


--
-- Name: stackmember; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.stackmember (
    id integer NOT NULL,
    device_id integer NOT NULL,
    hardware_id character varying(64) NOT NULL,
    member_no integer,
    priority integer
);


ALTER TABLE public.stackmember OWNER TO cnaas;

--
-- Name: stackmember_id_seq; Type: SEQUENCE; Schema: public; Owner: cnaas
--

CREATE SEQUENCE public.stackmember_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.stackmember_id_seq OWNER TO cnaas;

--
-- Name: stackmember_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cnaas
--

ALTER SEQUENCE public.stackmember_id_seq OWNED BY public.stackmember.id;


--
-- Name: device id; Type: DEFAULT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.device ALTER COLUMN id SET DEFAULT nextval('public.device_id_seq'::regclass);


--
-- Name: job id; Type: DEFAULT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.job ALTER COLUMN id SET DEFAULT nextval('public.job_id_seq'::regclass);


--
-- Name: linknet id; Type: DEFAULT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.linknet ALTER COLUMN id SET DEFAULT nextval('public.linknet_id_seq'::regclass);


--
-- Name: mgmtdomain id; Type: DEFAULT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.mgmtdomain ALTER COLUMN id SET DEFAULT nextval('public.mgmtdomain_id_seq'::regclass);


--
-- Name: site id; Type: DEFAULT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.site ALTER COLUMN id SET DEFAULT nextval('public.site_id_seq'::regclass);


--
-- Name: stackmember id; Type: DEFAULT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.stackmember ALTER COLUMN id SET DEFAULT nextval('public.stackmember_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.alembic_version (version_num) FROM stdin;
b7629362583c
\.


--
-- Data for Name: apscheduler_jobs; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.apscheduler_jobs (id, next_run_time, job_state) FROM stdin;
\.


--
-- Data for Name: device; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.device (id, hostname, site_id, description, management_ip, dhcp_ip, serial, ztp_mac, platform, vendor, model, os_version, synchronized, state, device_type, last_seen, confhash, infra_ip, oob_ip, port) FROM stdin;
2	eosdist2	\N	\N	10.100.3.102	\N	\N	\N	eos	\N	\N	\N	f	MANAGED	DIST	2022-03-21 13:35:27.10143	\N	10.199.0.1	\N	\N
3	eosaccess	\N	\N	10.0.6.6	\N		0800275C091F	eos	Arista	vEOS	4.21.1.1F-10146868.42111F	t	MANAGED	ACCESS	2022-03-21 13:38:50.228624	0fe2ef9c6f1a7689a0d38984ae322ac865071e6e63716b4e9609a07b10078104	\N	\N	\N
1	eosdist1	\N	\N	10.100.3.101	\N	aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1234	\N	eos	Arista	vEOS	4.22.3M-14418192.4223M	f	MANAGED	DIST	2022-03-21 13:38:53.536576	\N	10.199.0.0	\N	\N
\.


--
-- Data for Name: interface; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.interface (device_id, name, configtype, data) FROM stdin;
3	Ethernet3	ACCESS_UPLINK	{"neighbor": "eosdist2"}
3	Ethernet2	ACCESS_UPLINK	{"neighbor": "eosdist1"}
3	Ethernet1	ACCESS_AUTO	{"vxlan": "student1", "description": "test_03_interfaces"}
\.


--
-- Data for Name: job; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.job (id, status, scheduled_time, start_time, finish_time, function_name, scheduled_by, comment, ticket_ref, next_job_id, result, exception, finished_devices, change_score, start_arguments) FROM stdin;
1	FINISHED	2022-03-21 13:35:26.593863	2022-03-21 13:35:26.591082	2022-03-21 13:35:26.767524	refresh_repo	admin	\N	\N	\N	{"message": "Commit 805d200d9a58d586bd6f34ccbde4b10328fb2c24 master by Johan Marcusson at 2021-08-27 14:41:39+02:00\\n", "repository": "TEMPLATES"}	\N	[]	\N	\N
2	FINISHED	2022-03-21 13:35:26.813053	2022-03-21 13:35:26.8108	2022-03-21 13:35:27.035967	refresh_repo	admin	\N	\N	\N	{"message": "Commit 3099bae0e96eafe50900805ee8f6d8c4c08745c9 master by Johan Marcusson at 2022-03-14 16:56:03+01:00\\n", "repository": "SETTINGS"}	\N	[]	\N	\N
3	FINISHED	2022-03-21 13:37:01.920596	2022-03-21 13:37:01.970904	2022-03-21 13:37:05.726646	discover_device	admin	\N	\N	\N	{"devices": {"mac-0800275C091F": {"failed": false, "job_tasks": [{"diff": "", "failed": false, "result": {"facts": {"fqdn": "mac-0800275C091F", "model": "vEOS", "uptime": 246, "vendor": "Arista", "hostname": "mac-0800275C091F", "os_version": "4.21.1.1F-10146868.42111F", "serial_number": "", "interface_list": ["Ethernet1", "Ethernet2", "Ethernet3", "Management1", "Port-Channel1", "Vlan1", "Vlan600"]}}, "task_name": "napalm_get"}]}}}	\N	[]	\N	{"dhcp_ip": "192.168.0.240", "ztp_mac": "0800275C091F", "iteration": 1}
4	FINISHED	2022-03-21 13:37:07.123738	2022-03-21 13:37:07.149019	2022-03-21 13:38:05.14997	init_access_device_step1	admin	\N	\N	5	{"devices": {"eosaccess": {"failed": true, "job_tasks": [{"diff": "", "failed": true, "result": "Subtask: napalm_get (failed)\\n", "task_name": "push_base_management"}, {"diff": "", "failed": false, "result": "Device certificate installed for eosaccess", "task_name": "ztp_device_cert"}, {"diff": "", "failed": false, "result": "\\n!\\n!\\nhostname eosaccess\\n!\\nusername admin privilege 15 role network-admin secret sha512 $6$NfD5eWiya9A.EgJF$qaW2.KvCz9oW0daVPqxQrUN5UYb4NN7URw42DMHqtHi7OSZ3eQGQBBvkYH.ZzO3wb2TAqGFBIZAVSRmvxeEvF1\\n!\\naaa authorization exec default local\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\n\\nradius-server host 10.100.2.3 key kaka\\n!\\naaa group server radius cnaas-nac\\n  server 10.100.2.3\\n!\\naaa authentication dot1x default group cnaas-nac\\ndot1x system-auth-control\\n!\\nmanagement security\\n ssl profile cnaas\\n  certificate cnaasnms.crt key cnaasnms.key\\n!\\nmanagement api http-commands\\n no shutdown\\n protocol https ssl profile cnaas\\n!\\nsnmp-server community public ro\\n!\\nvlan 600\\ninterface vlan 600\\n no shutdown\\n ip address 10.0.6.6/24\\n!\\nip route 0.0.0.0 0.0.0.0 10.0.6.1\\n!\\nntp server 194.58.202.148\\n!\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\nerrdisable recovery cause bpduguard\\nerrdisable recovery cause lacp-rate-limit\\nerrdisable recovery cause link-flap\\nerrdisable recovery cause no-internal-vlan\\nerrdisable recovery cause portchannelguard\\n!\\n\\nvlan 500\\n name STUDENT\\nvlan 501\\n name STUDENT2\\n!\\nvlan 13\\n name quarantine\\n\\n\\n!\\n\\ninterface Ethernet1\\n\\n description DOT1X\\n ! poe reboot action maintain\\n switchport\\n switchport mode access\\n switchport access vlan 13\\n !spanning-tree bpduguard enable\\n spanning-tree portfast edge\\n !dot1x pae authenticator\\n !dot1x authentication failure action traffic allow vlan 13\\n !dot1x port-control auto\\n ! dot1x host-mode single-host\\n ! dot1x eapol disabled\\n !dot1x mac based authentication\\n\\ninterface Ethernet2\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface Ethernet3\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface port-channel 1\\n description UPLINK\\n!\\n\\n", "task_name": "Generate initial device config"}, {"diff": "", "failed": true, "result": "Traceback (most recent call last):\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/eapilib.py\\", line 447, in send\\n    response_content = response.read()\\n  File \\"/usr/lib/python3.7/http/client.py\\", line 468, in read\\n    return self._readall_chunked()\\n  File \\"/usr/lib/python3.7/http/client.py\\", line 575, in _readall_chunked\\n    chunk_left = self._get_chunk_left()\\n  File \\"/usr/lib/python3.7/http/client.py\\", line 558, in _get_chunk_left\\n    chunk_left = self._read_next_chunk_size()\\n  File \\"/usr/lib/python3.7/http/client.py\\", line 518, in _read_next_chunk_size\\n    line = self.fp.readline(_MAXLINE + 1)\\n  File \\"/usr/lib/python3.7/socket.py\\", line 589, in readinto\\n    return self._sock.recv_into(b)\\n  File \\"/usr/lib/python3.7/ssl.py\\", line 1052, in recv_into\\n    return self.read(nbytes, buffer)\\n  File \\"/usr/lib/python3.7/ssl.py\\", line 911, in read\\n    return self._sslobj.read(len, buffer)\\nsocket.timeout: The read operation timed out\\n\\nDuring handling of the above exception, another exception occurred:\\n\\nTraceback (most recent call last):\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/nornir/core/task.py\\", line 99, in start\\n    r = self.task(self, **self.params)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/nornir_napalm/plugins/tasks/napalm_configure.py\\", line 39, in napalm_configure\\n    device.commit_config()\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/napalm/eos/eos.py\\", line 388, in commit_config\\n    self.device.run_commands(commands)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/napalm/eos/pyeapi_syntax_wrapper.py\\", line 42, in run_commands\\n    return super(Node, self).run_commands(commands, *args, **kwargs)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/client.py\\", line 771, in run_commands\\n    response = self._connection.execute(commands, encoding, **kwargs)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/eapilib.py\\", line 554, in execute\\n    response = self.send(request)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/eapilib.py\\", line 483, in send\\n    raise ConnectionError(str(self), error_msg)\\npyeapi.eapilib.ConnectionError: Socket error during eAPI connection: The read operation timed out\\n", "task_name": "Push base management config"}, {"diff": "", "failed": true, "result": "Traceback (most recent call last):\\n  File \\"./cnaas_nms/confpush/init_device.py\\", line 104, in push_base_management\\n    dry_run=False\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/nornir/core/task.py\\", line 174, in run\\n    raise NornirSubTaskError(task=run_task, result=r)\\nnornir.core.exceptions.NornirSubTaskError: Subtask: Push base management config (failed)\\n\\n\\nDuring handling of the above exception, another exception occurred:\\n\\nTraceback (most recent call last):\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/eapilib.py\\", line 440, in send\\n    self.transport.endheaders(message_body=data)\\n  File \\"/usr/lib/python3.7/http/client.py\\", line 1255, in endheaders\\n    self._send_output(message_body, encode_chunked=encode_chunked)\\n  File \\"/usr/lib/python3.7/http/client.py\\", line 1030, in _send_output\\n    self.send(msg)\\n  File \\"/usr/lib/python3.7/http/client.py\\", line 970, in send\\n    self.connect()\\n  File \\"/usr/lib/python3.7/http/client.py\\", line 1415, in connect\\n    super().connect()\\n  File \\"/usr/lib/python3.7/http/client.py\\", line 942, in connect\\n    (self.host,self.port), self.timeout, self.source_address)\\n  File \\"/usr/lib/python3.7/socket.py\\", line 727, in create_connection\\n    raise err\\n  File \\"/usr/lib/python3.7/socket.py\\", line 716, in create_connection\\n    sock.connect(sa)\\nOSError: [Errno 113] No route to host\\n\\nDuring handling of the above exception, another exception occurred:\\n\\nTraceback (most recent call last):\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/nornir/core/task.py\\", line 99, in start\\n    r = self.task(self, **self.params)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/nornir_napalm/plugins/tasks/napalm_get.py\\", line 44, in napalm_get\\n    result[g] = method(**options)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/napalm/eos/eos.py\\", line 445, in get_facts\\n    result = self.device.run_commands(commands)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/napalm/eos/pyeapi_syntax_wrapper.py\\", line 42, in run_commands\\n    return super(Node, self).run_commands(commands, *args, **kwargs)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/client.py\\", line 771, in run_commands\\n    response = self._connection.execute(commands, encoding, **kwargs)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/eapilib.py\\", line 554, in execute\\n    response = self.send(request)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/eapilib.py\\", line 483, in send\\n    raise ConnectionError(str(self), error_msg)\\npyeapi.eapilib.ConnectionError: Socket error during eAPI connection: [Errno 113] No route to host\\n", "task_name": "napalm_get"}]}}}	\N	[]	\N	{"device_id": 3, "new_hostname": "eosaccess"}
5	FINISHED	2022-03-21 13:38:35.139589	2022-03-21 13:38:35.154075	2022-03-21 13:38:36.591212	init_device_step2	unknown	\N	\N	\N	{"devices": {"eosaccess": {"failed": false, "job_tasks": [{"diff": "", "failed": false, "result": {"facts": {"fqdn": "eosaccess", "model": "vEOS", "uptime": 340, "vendor": "Arista", "hostname": "eosaccess", "os_version": "4.21.1.1F-10146868.42111F", "serial_number": "", "interface_list": ["Ethernet1", "Ethernet2", "Ethernet3", "Management1", "Port-Channel1", "Vlan600"]}}, "task_name": "napalm_get"}]}}}	\N	[]	\N	{"device_id": 3, "iteration": 1}
6	FINISHED	2022-03-21 13:38:37.962593	2022-03-21 13:38:37.978755	2022-03-21 13:38:40.523128	sync_devices (dry_run)	admin	\N	\N	\N	{"devices": {"eosaccess": {"failed": false, "job_tasks": [{"diff": "", "failed": false, "result": null, "task_name": "push_sync_device"}, {"diff": "", "failed": false, "result": "\\n!\\n!\\nhostname eosaccess\\n!\\nusername admin privilege 15 role network-admin secret sha512 $6$NfD5eWiya9A.EgJF$qaW2.KvCz9oW0daVPqxQrUN5UYb4NN7URw42DMHqtHi7OSZ3eQGQBBvkYH.ZzO3wb2TAqGFBIZAVSRmvxeEvF1\\n!\\naaa authorization exec default local\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\n\\nradius-server host 10.100.2.3 key kaka\\n!\\naaa group server radius cnaas-nac\\n  server 10.100.2.3\\n!\\naaa authentication dot1x default group cnaas-nac\\ndot1x system-auth-control\\n!\\nmanagement security\\n ssl profile cnaas\\n  certificate cnaasnms.crt key cnaasnms.key\\n!\\nmanagement api http-commands\\n no shutdown\\n protocol https ssl profile cnaas\\n!\\nsnmp-server community public ro\\n!\\nvlan 600\\ninterface vlan 600\\n no shutdown\\n ip address 10.0.6.6/24\\n!\\nip route 0.0.0.0 0.0.0.0 10.0.6.1\\n!\\nntp server 194.58.202.148\\n!\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\nerrdisable recovery cause bpduguard\\nerrdisable recovery cause lacp-rate-limit\\nerrdisable recovery cause link-flap\\nerrdisable recovery cause no-internal-vlan\\nerrdisable recovery cause portchannelguard\\n!\\n\\nvlan 500\\n name STUDENT\\nvlan 501\\n name STUDENT2\\n!\\nvlan 13\\n name quarantine\\n\\n\\n!\\n\\ninterface Ethernet1\\n\\n description test_03_interfaces\\n ! poe reboot action maintain\\n switchport\\n switchport mode access\\n switchport access vlan 13\\n !spanning-tree bpduguard enable\\n spanning-tree portfast edge\\n !dot1x pae authenticator\\n !dot1x authentication failure action traffic allow vlan 13\\n !dot1x port-control auto\\n ! dot1x host-mode single-host\\n ! dot1x eapol disabled\\n !dot1x mac based authentication\\n\\n  description test_03_interfaces\\ninterface Ethernet2\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface Ethernet3\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface port-channel 1\\n description UPLINK\\n!\\n\\n", "task_name": "Generate device config"}, {"diff": "@@ -14,7 +14,7 @@\\n !\\n ntp server 194.58.202.148\\n !\\n-radius-server host 10.100.2.3 key 7 070420474F\\n+radius-server host 10.100.2.3 key 7 060D0E2A4D\\n !\\n aaa group server radius cnaas-nac\\n    server 10.100.2.3\\n@@ -46,7 +46,7 @@\\n    switchport mode trunk\\n !\\n interface Ethernet1\\n-   description DOT1X\\n+   description test_03_interfaces\\n    switchport access vlan 13\\n    spanning-tree portfast\\n !", "failed": false, "result": null, "task_name": "Sync device config"}]}}}	\N	["eosaccess"]	2	{"force": true, "resync": false, "dry_run": true, "auto_push": false, "hostnames": ["eosaccess"]}
8	FINISHED	2022-03-21 13:38:45.595472	2022-03-21 13:38:45.604863	2022-03-21 13:38:50.239443	sync_devices	unknown	\N	\N	\N	{"devices": {"eosaccess": {"failed": false, "job_tasks": [{"diff": "", "failed": false, "result": null, "task_name": "push_sync_device"}, {"diff": "", "failed": false, "result": "\\n!\\n!\\nhostname eosaccess\\n!\\nusername admin privilege 15 role network-admin secret sha512 $6$NfD5eWiya9A.EgJF$qaW2.KvCz9oW0daVPqxQrUN5UYb4NN7URw42DMHqtHi7OSZ3eQGQBBvkYH.ZzO3wb2TAqGFBIZAVSRmvxeEvF1\\n!\\naaa authorization exec default local\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\n\\nradius-server host 10.100.2.3 key kaka\\n!\\naaa group server radius cnaas-nac\\n  server 10.100.2.3\\n!\\naaa authentication dot1x default group cnaas-nac\\ndot1x system-auth-control\\n!\\nmanagement security\\n ssl profile cnaas\\n  certificate cnaasnms.crt key cnaasnms.key\\n!\\nmanagement api http-commands\\n no shutdown\\n protocol https ssl profile cnaas\\n!\\nsnmp-server community public ro\\n!\\nvlan 600\\ninterface vlan 600\\n no shutdown\\n ip address 10.0.6.6/24\\n!\\nip route 0.0.0.0 0.0.0.0 10.0.6.1\\n!\\nntp server 194.58.202.148\\n!\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\nerrdisable recovery cause bpduguard\\nerrdisable recovery cause lacp-rate-limit\\nerrdisable recovery cause link-flap\\nerrdisable recovery cause no-internal-vlan\\nerrdisable recovery cause portchannelguard\\n!\\n\\nvlan 500\\n name STUDENT\\nvlan 501\\n name STUDENT2\\n!\\nvlan 13\\n name quarantine\\n\\n\\n!\\n\\ninterface Ethernet1\\n\\n description test_03_interfaces\\n ! poe reboot action maintain\\n switchport\\n switchport mode access\\n switchport access vlan 13\\n !spanning-tree bpduguard enable\\n spanning-tree portfast edge\\n !dot1x pae authenticator\\n !dot1x authentication failure action traffic allow vlan 13\\n !dot1x port-control auto\\n ! dot1x host-mode single-host\\n ! dot1x eapol disabled\\n !dot1x mac based authentication\\n\\n  description test_03_interfaces\\ninterface Ethernet2\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface Ethernet3\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface port-channel 1\\n description UPLINK\\n!\\n\\n", "task_name": "Generate device config"}, {"diff": "@@ -14,7 +14,7 @@\\n !\\n ntp server 194.58.202.148\\n !\\n-radius-server host 10.100.2.3 key 7 070420474F\\n+radius-server host 10.100.2.3 key 7 030F5A0007\\n !\\n aaa group server radius cnaas-nac\\n    server 10.100.2.3\\n@@ -46,7 +46,7 @@\\n    switchport mode trunk\\n !\\n interface Ethernet1\\n-   description DOT1X\\n+   description test_03_interfaces\\n    switchport access vlan 13\\n    spanning-tree portfast\\n !", "failed": false, "result": null, "task_name": "Sync device config"}]}}}	\N	["eosaccess"]	2	{"force": false, "dry_run": false, "hostnames": ["eosaccess"]}
7	FINISHED	2022-03-21 13:38:43.057608	2022-03-21 13:38:43.081533	2022-03-21 13:38:45.613755	sync_devices (dry_run)	admin	\N	\N	8	{"devices": {"eosaccess": {"failed": false, "job_tasks": [{"diff": "", "failed": false, "result": null, "task_name": "push_sync_device"}, {"diff": "", "failed": false, "result": "\\n!\\n!\\nhostname eosaccess\\n!\\nusername admin privilege 15 role network-admin secret sha512 $6$NfD5eWiya9A.EgJF$qaW2.KvCz9oW0daVPqxQrUN5UYb4NN7URw42DMHqtHi7OSZ3eQGQBBvkYH.ZzO3wb2TAqGFBIZAVSRmvxeEvF1\\n!\\naaa authorization exec default local\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\n\\nradius-server host 10.100.2.3 key kaka\\n!\\naaa group server radius cnaas-nac\\n  server 10.100.2.3\\n!\\naaa authentication dot1x default group cnaas-nac\\ndot1x system-auth-control\\n!\\nmanagement security\\n ssl profile cnaas\\n  certificate cnaasnms.crt key cnaasnms.key\\n!\\nmanagement api http-commands\\n no shutdown\\n protocol https ssl profile cnaas\\n!\\nsnmp-server community public ro\\n!\\nvlan 600\\ninterface vlan 600\\n no shutdown\\n ip address 10.0.6.6/24\\n!\\nip route 0.0.0.0 0.0.0.0 10.0.6.1\\n!\\nntp server 194.58.202.148\\n!\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\nerrdisable recovery cause bpduguard\\nerrdisable recovery cause lacp-rate-limit\\nerrdisable recovery cause link-flap\\nerrdisable recovery cause no-internal-vlan\\nerrdisable recovery cause portchannelguard\\n!\\n\\nvlan 500\\n name STUDENT\\nvlan 501\\n name STUDENT2\\n!\\nvlan 13\\n name quarantine\\n\\n\\n!\\n\\ninterface Ethernet1\\n\\n description test_03_interfaces\\n ! poe reboot action maintain\\n switchport\\n switchport mode access\\n switchport access vlan 13\\n !spanning-tree bpduguard enable\\n spanning-tree portfast edge\\n !dot1x pae authenticator\\n !dot1x authentication failure action traffic allow vlan 13\\n !dot1x port-control auto\\n ! dot1x host-mode single-host\\n ! dot1x eapol disabled\\n !dot1x mac based authentication\\n\\n  description test_03_interfaces\\ninterface Ethernet2\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface Ethernet3\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface port-channel 1\\n description UPLINK\\n!\\n\\n", "task_name": "Generate device config"}, {"diff": "@@ -14,7 +14,7 @@\\n !\\n ntp server 194.58.202.148\\n !\\n-radius-server host 10.100.2.3 key 7 070420474F\\n+radius-server host 10.100.2.3 key 7 09474F0218\\n !\\n aaa group server radius cnaas-nac\\n    server 10.100.2.3\\n@@ -46,7 +46,7 @@\\n    switchport mode trunk\\n !\\n interface Ethernet1\\n-   description DOT1X\\n+   description test_03_interfaces\\n    switchport access vlan 13\\n    spanning-tree portfast\\n !", "failed": false, "result": null, "task_name": "Sync device config"}]}}}	\N	["eosaccess"]	2	{"force": false, "resync": false, "dry_run": true, "auto_push": true, "hostnames": ["eosaccess"]}
9	FINISHED	2022-03-21 13:38:53.223076	2022-03-21 13:38:53.248993	2022-03-21 13:38:53.550581	update_facts	admin	\N	\N	\N	{"diff": {"model": {"new": "vEOS", "old": null}, "serial": {"new": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1234", "old": null}, "vendor": {"new": "Arista", "old": null}, "os_version": {"new": "4.22.3M-14418192.4223M", "old": null}}}	\N	[]	\N	{"hostname": "eosdist1"}
10	FINISHED	2022-03-21 13:38:58.41184	2022-03-21 13:38:58.430283	2022-03-21 13:39:00.543511	sync_devices (dry_run)	admin	\N	\N	\N	{"devices": {"eosdist1": {"failed": true, "job_tasks": [{"diff": "", "failed": true, "result": "Subtask: Sync device config (failed)\\n", "task_name": "push_sync_device"}, {"diff": "", "failed": false, "result": "\\n!\\n!\\nhostname eosdist1\\n!\\nusername admin privilege 15 role network-admin secret sha512 $6$NfD5eWiya9A.EgJF$qaW2.KvCz9oW0daVPqxQrUN5UYb4NN7URw42DMHqtHi7OSZ3eQGQBBvkYH.ZzO3wb2TAqGFBIZAVSRmvxeEvF1\\n!\\naaa authorization exec default local\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.9.9\\n!\\n\\n!\\nmaintenance\\n   profile unit boot\\n      on-boot duration 360\\n   !\\n   unit eBGP_boot\\n      group bgp AllBgpNeighborVrf-MGMT\\n      group bgp AllBgpNeighborVrf-STUDENT\\n      group bgp AllBgpNeighborVrf-ROUTELEAK\\n      profile unit boot\\n!\\n\\n\\nvrf instance MGMT\\n!\\nmanagement security\\n ssl profile cnaas\\n  certificate cnaasnms.crt key cnaasnms.key\\n!\\nmanagement api http-commands\\n protocol https ssl profile cnaas\\n no shutdown\\n vrf MGMT\\n  no shutdown\\n!\\nmanagement api gnmi\\n transport grpc def\\n  no shutdown\\n  ssl profile cnaas\\n  vrf MGMT\\n!\\nerrdisable recovery cause bpduguard\\nerrdisable recovery cause hitless-reload-down\\nerrdisable recovery cause lacp-rate-limit\\nerrdisable recovery cause link-flap\\nerrdisable recovery cause portchannelguard\\n!\\nspanning-tree mode mstp\\n!\\nip routing\\nip routing vrf MGMT\\n!\\nip virtual-router mac-address aaaa.aaaa.aaaa\\n!\\nservice routing protocols model multi-agent\\n!\\nsnmp-server community public ro\\nsnmp-server vrf MGMT\\n!\\nntp server vrf MGMT 194.58.202.20\\nntp server vrf MGMT 194.58.202.148\\n!\\n!\\n\\nvlan 600\\n name mgmtdom-600\\n!\\nvlan 500\\n name STUDENT\\nvlan 502\\n name STUDENT34\\nvlan 503\\n name STUDENT34\\nvlan 501\\n name STUDENT2\\n\\n\\nvrf instance MGMT\\nvrf instance STUDENT\\nvrf instance ROUTELEAK\\n!\\nip routing vrf MGMT\\nipv6 unicast-routing vrf MGMT\\nip routing vrf STUDENT\\nipv6 unicast-routing vrf STUDENT\\nip routing vrf ROUTELEAK\\nipv6 unicast-routing vrf ROUTELEAK\\n!\\n\\ninterface Loopback0\\n no shutdown\\n ip address 10.199.0.0/32\\n!\\ninterface Loopback1\\n vrf MGMT\\n no shutdown\\n ip address 10.100.3.101/32\\n!\\ninterface Vlan600\\n vrf MGMT\\n ip address virtual 10.0.6.1/24\\n arp aging timeout 180\\n!\\ninterface Ethernet1\\n no switchport\\nvrf MGMT\\nip address 10.100.2.101/24\\nno lldp transmit\\nno lldp receive\\ninterface Ethernet2\\n description eosaccess\\n link-debounce time 20000 0\\n switchport\\n switchport mode trunk\\n channel-group 2 mode active\\n!\\ninterface Port-channel 2\\n description eosaccess\\n port-channel lacp fallback static\\n port-channel lacp fallback timeout 3\\n evpn ethernet-segment\\n  identifier 0033:3333:3333:3333:0103\\n  route-target import 00:03:00:03:01:03\\n lacp system-id 1234.5678.0103\\ninterface Ethernet3\\ninterface Vlan1\\n description ZTP\\nvrf MGMT\\nip address 192.168.0.1/24\\nip helper-address 10.100.2.2\\n!\\n!\\ninterface Vlan500\\n vrf STUDENT\\n description student1\\n ip address virtual 10.200.1.1/24\\n arp aging timeout 180\\n!\\ninterface Vlan502\\n vrf STUDENT\\n description student3\\n ip address virtual 10.202.1.1/24\\n arp aging timeout 180\\n!\\ninterface Vlan503\\n vrf STUDENT\\n description student4\\n ip address virtual 10.203.2.1/24\\n arp aging timeout 180\\n!\\ninterface Vlan501\\n vrf STUDENT\\n description student2\\n ip address virtual 10.201.1.1/24\\n ipv6 address virtual fe80::1/64\\n arp aging timeout 180\\n mtu 9100\\n!\\n!\\n!\\ninterface Vxlan1\\n vxlan source-interface Loopback0\\n vxlan udp-port 4789\\n vxlan vlan 500 vni 100500\\n vxlan vlan 502 vni 100502\\n vxlan vlan 503 vni 100503\\n vxlan vlan 501 vni 100501\\n vxlan vlan 600 vni 200600\\n vxlan vrf MGMT vni 100001\\n vxlan vrf STUDENT vni 100100\\n vxlan vrf ROUTELEAK vni 100200\\n!\\n\\n\\nrouter bgp 4200000000\\n router-id 10.199.0.0\\n no bgp default ipv4-unicast\\n maximum-paths 2\\n update wait-install\\n neighbor 10.199.0.1 remote-as 4200000001\\n neighbor 10.199.0.1 description eosdist2\\n neighbor 10.199.0.1 update-source Loopback0\\n neighbor 10.199.0.1 ebgp-multihop 3\\n neighbor 10.199.0.1 send-community\\n neighbor 10.199.0.1 bfd\\n neighbor 10.199.0.1 maximum-routes 0\\n!\\n address-family ipv4\\n   network 10.199.0.0/32\\n !\\n address-family evpn\\n   neighbor 10.199.0.1 activate\\n   neighbor 10.199.0.1 next-hop-unchanged\\n !\\n  vlan 500\\n  rd 10.199.0.0:500\\n  route-target both 1:500\\n  redistribute learned\\n  vlan 502\\n  rd 10.199.0.0:502\\n  route-target both 1:502\\n  redistribute learned\\n  vlan 503\\n  rd 10.199.0.0:503\\n  route-target both 1:503\\n  redistribute learned\\n  vlan 501\\n  rd 10.199.0.0:501\\n  route-target both 1:501\\n  redistribute learned\\n!\\n  vlan 600\\n  rd 10.199.0.0:600\\n  route-target both 1:600\\n  redistribute learned\\n!\\n  vrf MGMT\\n  rd 10.199.0.0:1\\n  route-target export evpn 2:1\\n  route-target import evpn 2:1\\n  redistribute connected\\n  redistribute static\\n\\n\\n  vrf STUDENT\\n  rd 10.199.0.0:100\\n  route-target export evpn 2:100\\n  route-target import evpn 2:100\\n  redistribute connected\\n  redistribute static\\n\\n     local-as 64551\\n      neighbor 10.131.11.12 remote-as 64521\\n      neighbor 10.131.11.12 route-map STUDENT-vas-in in\\n      neighbor 10.131.11.12 route-map STUDENT-vas-out out\\n      neighbor 10.131.11.12 maximum-routes 12000\\n      neighbor 10.131.11.12 description undefined\\n      address-family ipv4\\n        neighbor 10.131.11.12 activate\\n\\n  vrf ROUTELEAK\\n  rd 10.199.0.0:200\\n  route-target export evpn 2:200\\n  route-target import evpn 2:200\\n  route-target export evpn 1:6666\\n  route-target import evpn 1:5555\\n  route-target export evpn route-map export-map\\n  route-target import evpn route-map import-map\\n  redistribute connected\\n  redistribute static\\n\\n\\n\\nip prefix-list default-in\\n   seq 10 permit 0.0.0.0/0\\n!\\nip prefix-list larger_than_32\\n   seq 10 permit 0.0.0.0/0 le 31\\n!\\nroute-map default-only-in permit 10\\n   match ip address prefix-list default-in\\n!\\nroute-map vrf_prefixes-out permit 10\\n   match ip address prefix-list larger_than_32\\n!\\nroute-map vrf_prefixes-out permit 20\\n   match source-protocol connected\\n!\\nroute-map vrf_prefixes-out permit 30\\n   match source-protocol static\\n!\\nroute-map vrf_prefixes-out deny 1000\\n!\\nip prefix-list mgmt-in\\n   seq 10 permit 10.101.100.0/24\\n   seq 20 permit 192.168.222.0/24\\n!\\nip prefix-list mgmt-out\\n   seq 10 permit 10.101.2.0/24\\n   seq 20 permit 10.101.3.0/24\\n   seq 30 permit 10.101.4.0/24\\n   seq 40 permit 192.168.0.0/24\\n   seq 50 permit 192.168.2.0/24\\n   seq 60 permit 192.168.222.0/24\\n   seq 70 permit 192.168.223.0/24\\n   seq 80 permit 10.101.100.0/24\\n!\\nroute-map mgmt-in permit 10\\n   match ip address prefix-list mgmt-in\\n!\\nroute-map mgmt-out permit 10\\n   match ip address prefix-list mgmt-out\\n!\\n\\n ip route vrf MGMT 0.0.0.0/0 10.0.0.1 name my_route \\n ipv6 route vrf MGMT ::/0 Ethernet3 fe80::2 name undefined \\nrouter ospfv3 vrf STUDENT\\n router-id 10.199.0.0\\n passive-interface default\\n address-family ipv4\\n  redistribute bgp route-map MYMAP\\n address-family ipv6\\n\\n\\n", "task_name": "Generate device config"}, {"diff": "", "failed": true, "result": "Traceback (most recent call last):\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/napalm/eos/eos.py\\", line 329, in _load_config\\n    self.device.run_commands(commands, fn0039_transform=self.fn0039_config)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/napalm/eos/pyeapi_syntax_wrapper.py\\", line 42, in run_commands\\n    return super(Node, self).run_commands(commands, *args, **kwargs)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/client.py\\", line 771, in run_commands\\n    response = self._connection.execute(commands, encoding, **kwargs)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/eapilib.py\\", line 554, in execute\\n    response = self.send(request)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/pyeapi/eapilib.py\\", line 473, in send\\n    raise CommandError(code, msg, command_error=err, output=out)\\npyeapi.eapilib.CommandError: Error [1002]: CLI command 120 of 237 'ipv6 address virtual fe80::1/64' failed: invalid command [Invalid input (at token 2: 'virtual')]\\n\\nDuring handling of the above exception, another exception occurred:\\n\\nTraceback (most recent call last):\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/nornir/core/task.py\\", line 99, in start\\n    r = self.task(self, **self.params)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/nornir_napalm/plugins/tasks/napalm_configure.py\\", line 32, in napalm_configure\\n    device.load_replace_candidate(filename=filename, config=configuration)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/napalm/eos/eos.py\\", line 340, in load_replace_candidate\\n    self._load_config(filename, config, True)\\n  File \\"/opt/cnaas/venv/lib/python3.7/site-packages/napalm/eos/eos.py\\", line 334, in _load_config\\n    raise ReplaceConfigException(msg)\\nnapalm.base.exceptions.ReplaceConfigException: Error [1002]: CLI command 120 of 237 'ipv6 address virtual fe80::1/64' failed: invalid command [Invalid input (at token 2: 'virtual')]\\n", "task_name": "Sync device config"}]}}}	\N	[]	100	{"force": true, "resync": false, "dry_run": true, "auto_push": false, "hostnames": ["eosdist1"]}
11	FINISHED	2022-03-21 13:39:03.830185	2022-03-21 13:39:03.839873	2022-03-21 13:39:06.361899	apply_config (dry_run)	admin	\N	\N	\N	{"devices": {"eosaccess": {"failed": false, "job_tasks": [{"diff": "", "failed": false, "result": null, "task_name": "push_static_config"}, {"diff": "@@ -14,7 +14,7 @@\\n !\\n ntp server 194.58.202.148\\n !\\n-radius-server host 10.100.2.3 key 7 030F5A0007\\n+radius-server host 10.100.2.3 key 7 0118070F5A\\n !\\n aaa group server radius cnaas-nac\\n    server 10.100.2.3", "failed": false, "result": null, "task_name": "Push static config"}]}}}	\N	[]	\N	{"config": "\\n!\\n!\\nhostname eosaccess\\n!\\nusername admin privilege 15 role network-admin secret sha512 $6$NfD5eWiya9A.EgJF$qaW2.KvCz9oW0daVPqxQrUN5UYb4NN7URw42DMHqtHi7OSZ3eQGQBBvkYH.ZzO3wb2TAqGFBIZAVSRmvxeEvF1\\n!\\naaa authorization exec default local\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\n\\nradius-server host 10.100.2.3 key kaka\\n!\\naaa group server radius cnaas-nac\\n  server 10.100.2.3\\n!\\naaa authentication dot1x default group cnaas-nac\\ndot1x system-auth-control\\n!\\nmanagement security\\n ssl profile cnaas\\n  certificate cnaasnms.crt key cnaasnms.key\\n!\\nmanagement api http-commands\\n no shutdown\\n protocol https ssl profile cnaas\\n!\\nsnmp-server community public ro\\n!\\nvlan 600\\ninterface vlan 600\\n no shutdown\\n ip address 10.0.6.6/24\\n!\\nip route 0.0.0.0 0.0.0.0 10.0.6.1\\n!\\nntp server 194.58.202.148\\n!\\n!\\nip access-list standard snmp-clients\\npermit host 10.100.3.3\\n!\\nerrdisable recovery cause bpduguard\\nerrdisable recovery cause lacp-rate-limit\\nerrdisable recovery cause link-flap\\nerrdisable recovery cause no-internal-vlan\\nerrdisable recovery cause portchannelguard\\n!\\n\\nvlan 500\\n name STUDENT\\nvlan 501\\n name STUDENT2\\n!\\nvlan 13\\n name quarantine\\n\\n\\n!\\n\\ninterface Ethernet1\\n\\n description test_03_interfaces\\n ! poe reboot action maintain\\n switchport\\n switchport mode access\\n switchport access vlan 13\\n !spanning-tree bpduguard enable\\n spanning-tree portfast edge\\n !dot1x pae authenticator\\n !dot1x authentication failure action traffic allow vlan 13\\n !dot1x port-control auto\\n ! dot1x host-mode single-host\\n ! dot1x eapol disabled\\n !dot1x mac based authentication\\n\\n  description test_03_interfaces\\ninterface Ethernet2\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface Ethernet3\\n switchport\\n switchport mode trunk\\n channel-group 1 mode active\\n  description UPLINK\\ninterface port-channel 1\\n description UPLINK\\n!\\n\\n", "dry_run": true, "hostname": "eosaccess"}
12	FINISHED	2022-03-21 13:39:08.899466	2022-03-21 13:39:08.91706	2022-03-21 13:39:09.608637	update_interfacedb	admin	\N	\N	\N	{"interfaces": []}	\N	[]	\N	{"replace": false, "hostname": "eosaccess", "delete_all": false, "mlag_peer_hostname": null}
13	ABORTED	2022-03-21 13:39:14.039006	2022-03-21 13:39:14.056687	2022-03-21 13:39:44.181194	device_upgrade	admin	\N	\N	\N	{"devices": {"eosdist1": {"failed": false, "job_tasks": [{"diff": "", "failed": false, "result": null, "task_name": "device_upgrade_task"}, {"diff": "", "failed": false, "result": "Post-flight aborted", "task_name": "arista_post_flight_check"}]}, "eosdist2": {"failed": false, "job_tasks": [{"diff": "", "failed": false, "result": null, "task_name": "device_upgrade_task"}, {"diff": "", "failed": false, "result": "Post-flight aborted", "task_name": "arista_post_flight_check"}]}}}	\N	["eosdist1", "eosdist2"]	\N	{"url": "", "group": "DIST", "post_flight": true, "post_waittime": 30}
14	ABORTED	2022-03-21 13:40:14.259029	\N	2022-03-21 13:39:47.331499	device_upgrade	admin	\N	\N	\N	{"message": "unit test abort_scheduled_job (aborted by admin)"}	\N	\N	\N	{"url": "", "group": "DIST", "post_flight": true, "post_waittime": 30}
\.


--
-- Data for Name: joblock; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.joblock (name, start_time, abort, job_id) FROM stdin;
\.


--
-- Data for Name: linknet; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.linknet (id, ipv4_network, device_a_id, device_a_ip, device_a_port, device_b_id, device_b_ip, device_b_port, site_id, description) FROM stdin;
1	\N	2	\N	Ethernet2	3	\N	Ethernet3	\N	\N
2	\N	3	\N	Ethernet2	1	\N	Ethernet2	\N	\N
\.


--
-- Data for Name: mgmtdomain; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.mgmtdomain (id, ipv4_gw, device_a_id, device_a_ip, device_b_id, device_b_ip, site_id, vlan, description, esi_mac) FROM stdin;
1	10.0.6.1/24	1	\N	2	\N	\N	600	\N	\N
\.


--
-- Data for Name: reservedip; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.reservedip (device_id, ip, last_seen) FROM stdin;
\.


--
-- Data for Name: site; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.site (id, description) FROM stdin;
1	default
\.


--
-- Data for Name: stackmember; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.stackmember (id, device_id, hardware_id, member_no, priority) FROM stdin;
\.


--
-- Name: device_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.device_id_seq', 3, true);


--
-- Name: job_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.job_id_seq', 14, true);


--
-- Name: linknet_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.linknet_id_seq', 2, true);


--
-- Name: mgmtdomain_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.mgmtdomain_id_seq', 1, true);


--
-- Name: site_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.site_id_seq', 2, true);


--
-- Name: stackmember_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.stackmember_id_seq', 1, false);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: apscheduler_jobs apscheduler_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.apscheduler_jobs
    ADD CONSTRAINT apscheduler_jobs_pkey PRIMARY KEY (id);


--
-- Name: device device_hostname_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.device
    ADD CONSTRAINT device_hostname_key UNIQUE (hostname);


--
-- Name: device device_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.device
    ADD CONSTRAINT device_pkey PRIMARY KEY (id);


--
-- Name: interface interface_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.interface
    ADD CONSTRAINT interface_pkey PRIMARY KEY (device_id, name);


--
-- Name: job job_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.job
    ADD CONSTRAINT job_pkey PRIMARY KEY (id);


--
-- Name: joblock joblock_job_id_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.joblock
    ADD CONSTRAINT joblock_job_id_key UNIQUE (job_id);


--
-- Name: joblock joblock_name_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.joblock
    ADD CONSTRAINT joblock_name_key UNIQUE (name);


--
-- Name: linknet linknet_device_a_id_device_a_port_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.linknet
    ADD CONSTRAINT linknet_device_a_id_device_a_port_key UNIQUE (device_a_id, device_a_port);


--
-- Name: linknet linknet_device_b_id_device_b_port_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.linknet
    ADD CONSTRAINT linknet_device_b_id_device_b_port_key UNIQUE (device_b_id, device_b_port);


--
-- Name: linknet linknet_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.linknet
    ADD CONSTRAINT linknet_pkey PRIMARY KEY (id);


--
-- Name: mgmtdomain mgmtdomain_device_a_id_device_b_id_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.mgmtdomain
    ADD CONSTRAINT mgmtdomain_device_a_id_device_b_id_key UNIQUE (device_a_id, device_b_id);


--
-- Name: mgmtdomain mgmtdomain_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.mgmtdomain
    ADD CONSTRAINT mgmtdomain_pkey PRIMARY KEY (id);


--
-- Name: reservedip reservedip_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.reservedip
    ADD CONSTRAINT reservedip_pkey PRIMARY KEY (device_id);


--
-- Name: site site_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.site
    ADD CONSTRAINT site_pkey PRIMARY KEY (id);


--
-- Name: stackmember stackmember_device_id_hardware_id_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.stackmember
    ADD CONSTRAINT stackmember_device_id_hardware_id_key UNIQUE (device_id, hardware_id);


--
-- Name: stackmember stackmember_device_id_member_no_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.stackmember
    ADD CONSTRAINT stackmember_device_id_member_no_key UNIQUE (device_id, member_no);


--
-- Name: stackmember stackmember_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.stackmember
    ADD CONSTRAINT stackmember_pkey PRIMARY KEY (id);


--
-- Name: ix_apscheduler_jobs_next_run_time; Type: INDEX; Schema: public; Owner: cnaas
--

CREATE INDEX ix_apscheduler_jobs_next_run_time ON public.apscheduler_jobs USING btree (next_run_time);


--
-- Name: ix_interface_device_id; Type: INDEX; Schema: public; Owner: cnaas
--

CREATE INDEX ix_interface_device_id ON public.interface USING btree (device_id);


--
-- Name: ix_job_finish_time; Type: INDEX; Schema: public; Owner: cnaas
--

CREATE INDEX ix_job_finish_time ON public.job USING btree (finish_time);


--
-- Name: ix_job_status; Type: INDEX; Schema: public; Owner: cnaas
--

CREATE INDEX ix_job_status ON public.job USING btree (status);


--
-- Name: ix_job_ticket_ref; Type: INDEX; Schema: public; Owner: cnaas
--

CREATE INDEX ix_job_ticket_ref ON public.job USING btree (ticket_ref);


--
-- Name: ix_reservedip_device_id; Type: INDEX; Schema: public; Owner: cnaas
--

CREATE INDEX ix_reservedip_device_id ON public.reservedip USING btree (device_id);


--
-- Name: device device_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.device
    ADD CONSTRAINT device_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.site(id);


--
-- Name: interface interface_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.interface
    ADD CONSTRAINT interface_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.device(id);


--
-- Name: job job_next_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.job
    ADD CONSTRAINT job_next_job_id_fkey FOREIGN KEY (next_job_id) REFERENCES public.job(id);


--
-- Name: joblock joblock_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.joblock
    ADD CONSTRAINT joblock_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.job(id);


--
-- Name: linknet linknet_device_a_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.linknet
    ADD CONSTRAINT linknet_device_a_id_fkey FOREIGN KEY (device_a_id) REFERENCES public.device(id);


--
-- Name: linknet linknet_device_b_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.linknet
    ADD CONSTRAINT linknet_device_b_id_fkey FOREIGN KEY (device_b_id) REFERENCES public.device(id);


--
-- Name: linknet linknet_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.linknet
    ADD CONSTRAINT linknet_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.site(id);


--
-- Name: mgmtdomain mgmtdomain_device_a_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.mgmtdomain
    ADD CONSTRAINT mgmtdomain_device_a_id_fkey FOREIGN KEY (device_a_id) REFERENCES public.device(id);


--
-- Name: mgmtdomain mgmtdomain_device_b_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.mgmtdomain
    ADD CONSTRAINT mgmtdomain_device_b_id_fkey FOREIGN KEY (device_b_id) REFERENCES public.device(id);


--
-- Name: mgmtdomain mgmtdomain_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.mgmtdomain
    ADD CONSTRAINT mgmtdomain_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.site(id);


--
-- Name: reservedip reservedip_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.reservedip
    ADD CONSTRAINT reservedip_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.device(id);


--
-- Name: stackmember stackmember_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.stackmember
    ADD CONSTRAINT stackmember_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.device(id);


--
-- PostgreSQL database dump complete
--

