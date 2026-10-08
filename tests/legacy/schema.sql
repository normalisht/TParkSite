CREATE TABLE admin (
	id INTEGER NOT NULL,
	name VARCHAR(128),
	email VARCHAR(128),
	password VARCHAR(64),
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_admin_id ON admin (id);
CREATE TABLE comment (
	id INTEGER NOT NULL,
	name VARCHAR(128),
	text TEXT,
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_comment_id ON comment (id);
CREATE TABLE service_category (
	id INTEGER NOT NULL,
	service_id INTEGER,
	category_id INTEGER, number INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(category_id) REFERENCES category (id),
	FOREIGN KEY(service_id) REFERENCES service (id)
);
CREATE UNIQUE INDEX ix_service_category_id ON service_category (id);
CREATE TABLE employee (
	id INTEGER NOT NULL,
	photo VARCHAR(1024),
	name VARCHAR(128),
	position VARCHAR(64),
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_employee_id ON employee (id);
CREATE TABLE partner (
	id INTEGER NOT NULL,
	name VARCHAR(128),
	link VARCHAR(1024),
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_partner_id ON partner (id);
CREATE TABLE price (
	id INTEGER NOT NULL,
	service_id INTEGER,
	price VARCHAR(128), time VARCHAR(128),
	PRIMARY KEY (id),
	FOREIGN KEY(service_id) REFERENCES service (id)
);
CREATE UNIQUE INDEX ix_price_id ON price (id);
CREATE TABLE text (id INTEGER NOT NULL, title VARCHAR (64), text TEXT, status BOOLEAN, PRIMARY KEY (id), UNIQUE (title));
CREATE UNIQUE INDEX ix_text_id ON text (id);
CREATE TABLE event (id INTEGER NOT NULL, title VARCHAR (128), date DATE, link VARCHAR (1024), description TEXT, text_color VARCHAR(16), after_date BOOLEAN, PRIMARY KEY (id));
CREATE UNIQUE INDEX ix_event_id ON event (id);
CREATE TABLE "service" (
	id INTEGER NOT NULL,
	name TEXT(128),
	price TEXT(8),
	time TEXT(128),
	status BOOLEAN,
	short_description TEXT(512),
	description TEXT,
	next BOOLEAN,
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_service_id ON service (id);
CREATE TABLE type (
	id INTEGER NOT NULL,
	name VARCHAR(128),
	number INTEGER,
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_type_id ON type (id);
CREATE TABLE category_type (
	id INTEGER NOT NULL,
	type_id INTEGER,
	category_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(category_id) REFERENCES category (id),
	FOREIGN KEY(type_id) REFERENCES type (id)
);
CREATE UNIQUE INDEX ix_category_type_id ON category_type (id);
CREATE TABLE category (id INTEGER NOT NULL, name TEXT (128), status BOOLEAN, description TEXT, number INTEGER, PRIMARY KEY (id));
CREATE UNIQUE INDEX ix_category_id ON category (id);
CREATE INDEX ix_category_number ON category (number);
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL,
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
