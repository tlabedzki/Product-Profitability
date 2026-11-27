# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-11-27

### Added
- README section "Why these tools": what each key tool does in the project, why it fits how the data is read and
  rebuilt from a fresh clone, and which alternative was considered and why it was dropped.

## [1.0.0] - 2026-11-24

### Added
- Margin cascade of every product: price-list margin, discounts, returns, shipping, payment fees, affiliate
  commission and true margin, with order costs spread over lines in DuckDB SQL and reconciled to the grosz.
- Loss-making bestsellers with the cost behind each loss and one move: change the price, end free delivery or delist.
- Dash + Mantine app in the Data-Generator look: shop and category cascade, live rules, product card with its orders.
- Shop data from Data-Generator v1.7.1 (`scripts/get_data.py`), with a mock of the cost columns for older releases.
- README charts, app screenshots and numbers from one script (`scripts/make_charts.py`, English or Polish).
- README, charts, animation and column notes in English for the public release.
- Animated README hero (`scripts/make_demo_svg.py`): the bestseller slider moves from the top 500 to the top 200 and a
  product card opens from the table; light and dark browser frame, a still end state with reduced motion.
- The app reads the sliders and the product card from the address (`/?bestsellers=200&rise=15&product=<id>`).
