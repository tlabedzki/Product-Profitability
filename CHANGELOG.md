# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Margin cascade of every product: price-list margin, discounts, returns, shipping, payment fees, affiliate
  commission and true margin, with order costs spread over lines in DuckDB SQL and reconciled to the grosz.
- Loss-making bestsellers with the cost behind each loss and one move: change the price, end free delivery or delist.
- Dash + Mantine app in the Data-Generator look: shop and category cascade, live rules, product card with its orders.
- Shop data from Data-Generator v1.7.1 (`scripts/get_data.py`), with a mock of the cost columns for older releases.
- README charts, app screenshots and numbers from one script (`scripts/make_charts.py`, Polish or English).
