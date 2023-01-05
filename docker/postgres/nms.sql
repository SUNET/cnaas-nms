--
-- PostgreSQL database dump
--

-- Dumped from database version 11.5 (Debian 11.5-3.pgdg90+1)
-- Dumped by pg_dump version 11.5 (Debian 11.5-3.pgdg90+1)

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
    'ACCESS_AUTO',
    'ACCESS_UNTAGGED',
    'ACCESS_TAGGED',
    'ACCESS_UPLINK'
);


ALTER TYPE public.interfaceconfigtype OWNER TO cnaas;

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
-- Name: joblock; Type: TABLE; Schema: public; Owner: cnaas
--

CREATE TABLE public.joblock (
    jobid character varying(24) NOT NULL,
    name character varying(32) NOT NULL,
    start_time timestamp without time zone,
    abort boolean
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
-- Name: device id; Type: DEFAULT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.device ALTER COLUMN id SET DEFAULT nextval('public.device_id_seq'::regclass);


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
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.alembic_version (version_num) FROM stdin;
9478bbaf8010
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
\.


--
-- Data for Name: interface; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.interface (device_id, name, configtype, data) FROM stdin;
\.


--
-- Data for Name: joblock; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.joblock (jobid, name, start_time, abort) FROM stdin;
\.


--
-- Data for Name: linknet; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.linknet (id, ipv4_network, device_a_id, device_a_ip, device_a_port, device_b_id, device_b_ip, device_b_port, site_id, description) FROM stdin;
\.


--
-- Data for Name: mgmtdomain; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.mgmtdomain (id, ipv4_gw, device_a_id, device_a_ip, device_b_id, device_b_ip, site_id, vlan, description, esi_mac) FROM stdin;
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
-- Name: site_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.site_id_seq', 2, true);


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
-- Name: joblock joblock_jobid_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.joblock
    ADD CONSTRAINT joblock_jobid_key UNIQUE (jobid);


--
-- Name: joblock joblock_name_key; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.joblock
    ADD CONSTRAINT joblock_name_key UNIQUE (name);


--
-- Name: joblock joblock_pkey; Type: CONSTRAINT; Schema: public; Owner: cnaas
--

ALTER TABLE ONLY public.joblock
    ADD CONSTRAINT joblock_pkey PRIMARY KEY (jobid);


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
-- Name: ix_apscheduler_jobs_next_run_time; Type: INDEX; Schema: public; Owner: cnaas
--

CREATE INDEX ix_apscheduler_jobs_next_run_time ON public.apscheduler_jobs USING btree (next_run_time);


--
-- Name: ix_interface_device_id; Type: INDEX; Schema: public; Owner: cnaas
--

CREATE INDEX ix_interface_device_id ON public.interface USING btree (device_id);


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
-- PostgreSQL database dump complete
--
