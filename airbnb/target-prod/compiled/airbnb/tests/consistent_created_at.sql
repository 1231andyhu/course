SELECT * FROM AIRBNB.PROD.dim_listings_cleansed l
INNER JOIN AIRBNB.PROD.fct_reviews r
USING (listing_id)
WHERE l.created_at > r.review_date