
    SELECT *
    FROM AIRBNB.PROD.dim_listings_cleansed
    WHERE minimum_nights <= 0 OR minimum_nights IS NULL
