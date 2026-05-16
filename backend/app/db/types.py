from sqlalchemy import BigInteger, Integer


id_type = BigInteger().with_variant(Integer, "sqlite")

