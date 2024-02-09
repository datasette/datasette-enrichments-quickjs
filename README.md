# datasette-enrichments-quickjs

[![PyPI](https://img.shields.io/pypi/v/datasette-enrichments-quickjs.svg)](https://pypi.org/project/datasette-enrichments-quickjs/)
[![Changelog](https://img.shields.io/github/v/release/datasette/datasette-enrichments-quickjs?include_prereleases&label=changelog)](https://github.com/datasette/datasette-enrichments-quickjs/releases)
[![Tests](https://github.com/datasette/datasette-enrichments-quickjs/actions/workflows/test.yml/badge.svg)](https://github.com/datasette/datasette-enrichments-quickjs/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/datasette/datasette-enrichments-quickjs/blob/main/LICENSE)

Enrich data with a custom JavaScript function

## Installation

Install this plugin in the same environment as Datasette.
```bash
datasette install datasette-enrichments-quickjs
```
## Usage

Usage instructions go here.

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:
```bash
cd datasette-enrichments-quickjs
python3 -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
pytest
```
