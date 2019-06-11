--
-- PostgreSQL database dump
--

-- Dumped from database version 10.7
-- Dumped by pg_dump version 10.7

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner:
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner:
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


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
    last_seen timestamp without time zone
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
    description character varying(255)
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
\.


--
-- Data for Name: apscheduler_jobs; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.apscheduler_jobs (id, next_run_time, job_state) FROM stdin;
\.


--
-- Data for Name: device; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.device (id, hostname, site_id, description, management_ip, dhcp_ip, serial, ztp_mac, platform, vendor, model, os_version, synchronized, state, device_type, last_seen) FROM stdin;
1	testdevice	1	Test device!	1.2.3.4	\N	\N	\N	eos	\N	\N	\N	f	UNKNOWN	UNKNOWN	2019-02-13 11:17:32.038118
6	mac-080027F60C55	\N	\N	\N	\N	\N	080027F60C55	eos	\N	\N	\N	f	DHCP_BOOT	UNKNOWN	2019-02-27 07:41:18.026646
13	eosaccess	\N	\N	10.0.6.6	10.0.0.20	\N	0800275C091F	eos	\N	\N	\N	f	MANAGED	ACCESS	2019-04-09 08:43:50.268572
9	eosdist	\N	\N	10.0.1.22	\N	\N	08002708a8be	eos	\N	\N	\N	t	MANAGED	DIST	2019-02-27 10:30:23.338681
12	eosdist2	\N	\N	10.0.1.23	\N	\N	08002708a8b0	eos	\N	\N	\N	t	MANAGED	DIST	2019-03-13 09:43:13.439735
\.


--
-- Data for Name: interface; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.interface (device_id, name, configtype, data) FROM stdin;
13	Ethernet3	ACCESS_UPLINK	\N
13	Ethernet2	ACCESS_UPLINK	\N
13	Ethernet1	ACCESS_AUTO	\N
\.


--
-- Data for Name: linknet; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.linknet (id, ipv4_network, device_a_id, device_a_ip, device_a_port, device_b_id, device_b_ip, device_b_port, site_id, description) FROM stdin;
6	\N	13	\N	Ethernet2	9	\N	Ethernet2	\N	\N
7	\N	13	\N	Ethernet3	12	\N	Ethernet2	\N	\N
\.


--
-- Data for Name: mgmtdomain; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.mgmtdomain (id, ipv4_gw, device_a_id, device_a_ip, device_b_id, device_b_ip, site_id, vlan, description) FROM stdin;
4	10.0.6.1/24	9	\N	12	\N	\N	600	\N
\.


--
-- Data for Name: site; Type: TABLE DATA; Schema: public; Owner: cnaas
--

COPY public.site (id, description) FROM stdin;
1	default
2	default
3	default
4	default
5	default
6	default
7	default
8	default
9	default
\.


--
-- Name: device_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.device_id_seq', 19, true);


--
-- Name: linknet_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.linknet_id_seq', 7, true);


--
-- Name: mgmtdomain_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.mgmtdomain_id_seq', 4, true);


--
-- Name: site_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cnaas
--

SELECT pg_catalog.setval('public.site_id_seq', 9, true);


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
-- PostgreSQL database dump complete
--
