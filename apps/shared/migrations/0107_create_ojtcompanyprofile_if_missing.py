from django.db import migrations


class Migration(migrations.Migration):

	dependencies = [
		('shared', '0106_merge_20251022_1706'),
	]

	operations = [
		migrations.RunSQL(
			"""
			CREATE TABLE IF NOT EXISTS shared_ojtcompanyprofile (
			    id SERIAL PRIMARY KEY,
			    user_id INTEGER NOT NULL UNIQUE REFERENCES shared_user (user_id) DEFERRABLE INITIALLY DEFERRED,
			    company_name VARCHAR(255),
			    company_address TEXT,
			    company_email VARCHAR(254),
			    company_contact VARCHAR(20),
			    contact_person VARCHAR(255),
			    position VARCHAR(255),
			    start_date DATE,
			    end_date DATE,
			    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
			    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
			);

			CREATE INDEX IF NOT EXISTS shared_ojtc_company_73494f_idx ON shared_ojtcompanyprofile (company_name);
			CREATE INDEX IF NOT EXISTS shared_ojtc_start_d_a99721_idx ON shared_ojtcompanyprofile (start_date);
			CREATE INDEX IF NOT EXISTS shared_ojtc_end_dat_3e437e_idx ON shared_ojtcompanyprofile (end_date);
			""",
			"""
			DROP TABLE IF EXISTS shared_ojtcompanyprofile CASCADE;
			""",
		),
	]


