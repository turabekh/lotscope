-- Synthetic demo dataset for local preview only. NOT real Philadelphia data.
-- Idempotent: removes its own rows (parcel numbers 888*, source 'demo') first.
BEGIN;

DELETE FROM parcel_verdict WHERE parcel_number LIKE '888%';
DELETE FROM sale WHERE parcel_number LIKE '888%';
DELETE FROM tax_status WHERE parcel_number LIKE '888%';
DELETE FROM parcel WHERE parcel_number LIKE '888%';
DELETE FROM zoning_district WHERE source = 'demo';

INSERT INTO zoning_district (code, category, source, geom_4326, geom_2272)
VALUES (
  'RSA-5', 'Residential', 'demo',
  ST_GeomFromText('POLYGON((-75.17 39.925,-75.17 39.935,-75.16 39.935,-75.16 39.925,-75.17 39.925))', 4326),
  ST_Transform(ST_GeomFromText('POLYGON((-75.17 39.925,-75.17 39.935,-75.16 39.935,-75.16 39.925,-75.17 39.925))', 4326), 2272)
);

INSERT INTO parcel (
  parcel_number, address, owner, base_zoning_code, lot_area_sqft, frontage_ft, depth_ft,
  market_value, is_vacant, is_city_owned, source, geom_4326, geom_2272
)
SELECT
  '88800000' || g,
  (1500 + 2 * g) || ' S BROAD ST',
  (ARRAY['Acme Land Holdings LLC','Jane Smith','John Developer','Smith Family Trust','City of Philadelphia'])[g],
  'RSA-5',
  (ARRAY[1600,1000,1100,1050,2000])[g],
  (ARRAY[18,16,16,16,20])[g],
  (ARRAY[90,62,68,65,100])[g],
  (ARRAY[120000,90000,95000,92000,140000])[g],
  TRUE,
  (g = 5),
  'demo',
  geom4326,
  ST_Transform(geom4326, 2272)
FROM generate_series(1, 5) AS g,
LATERAL (
  SELECT ST_GeomFromText(
    'POLYGON((' ||
    (-75.1650 + g * 0.0003) || ' 39.9300,' ||
    (-75.1650 + g * 0.0003) || ' 39.9302,' ||
    (-75.1648 + g * 0.0003) || ' 39.9302,' ||
    (-75.1648 + g * 0.0003) || ' 39.9300,' ||
    (-75.1650 + g * 0.0003) || ' 39.9300))', 4326) AS geom4326
) AS square;

INSERT INTO sale (parcel_number, document_id, document_type, sale_date, sale_price, source)
VALUES
  ('888000002', 'DEMO-2', 'DEED', '2024-05-01', 95000, 'demo'),
  ('888000003', 'DEMO-3', 'DEED', '2024-06-15', 110000, 'demo'),
  ('888000004', 'DEMO-4', 'DEED', '2024-07-20', 100000, 'demo');

INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, source)
VALUES ('888000001', TRUE, 22000, 4, 'demo');

INSERT INTO tax_status (parcel_number, is_delinquent, in_sheriff_sale, total_due, years_owed, source)
VALUES ('888000005', TRUE, TRUE, 45000, 6, 'demo');

COMMIT;
