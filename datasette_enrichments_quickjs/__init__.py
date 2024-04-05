from datasette_enrichments import Enrichment
from datasette import hookimpl
import json
import markupsafe
from quickjs import Function
import sqlite_utils
from wtforms import Form, StringField, TextAreaField, SelectField, ValidationError
from wtforms.validators import DataRequired


@hookimpl
def register_enrichments():
    return [QuickJsEnrichment()]


class QuickJsEnrichment(Enrichment):
    name = "JavaScript"
    slug = "quickjs"
    description = "Enrich data with a custom JavaScript function"

    async def initialize(self, datasette, db, table, config):
        # Ensure column exists
        if config["mode"] == "multi":
            # No need to create columns for multi mode
            return
        output_column = config["output_column"]
        column_type = config["output_column_type"].upper()

        def add_column_if_not_exists(conn):
            db = sqlite_utils.Database(conn)
            if output_column not in db[table].columns_dict:
                db[table].add_column(output_column, column_type)

        await db.execute_write_fn(add_column_if_not_exists)

    async def get_config_form(self, db, table):
        columns = await db.table_columns(table)
        bits = [
            "Define an enrich(row) JavaScript function taking an object and returning a value"
        ]
        bits.append("Row keys: {}".format(", ".join(columns)))

        class ConfigForm(Form):
            javascript = TextAreaField(
                "JavaScript function",
                description=markupsafe.Markup(
                    "<br>".join(markupsafe.escape(bit) for bit in bits)
                ),
                validators=[DataRequired(message="JavaScript function is required.")],
                default='function enrich(row) {\n  return JSON.stringify(row) + " enriched";\n}',
            )
            mode = SelectField(
                "Output mode",
                choices=[
                    ("single", "Store the function result in a single column"),
                    (
                        "multi",
                        "Return an object and store each key in a separate column",
                    ),
                ],
                validators=[DataRequired(message="A mode is required.")],
            )
            output_column = StringField(
                "Output column name",
                description="The column to store the output in - will be created if it does not exist.",
                validators=[DataRequired(message="Column is required.")],
                default="javascript_output",
            )
            output_column_type = SelectField(
                "Output column type",
                description="The type of the output column to create.",
                validators=[DataRequired(message="Column is required.")],
                default="text",
                choices=[
                    ("text", "Text"),
                    ("integer", "Integer"),
                    ("float", "Float"),
                ],
            )

            def validate_javascript(form, field):
                try:
                    function = Function("enrich", field.data)
                except Exception as e:
                    raise ValidationError("Invalid JavaScript function: {}".format(e))

        return ConfigForm

    async def enrich_batch(
        self,
        db,
        table,
        rows,
        pks,
        config,
    ):
        function = Function("enrich", config["javascript"])
        function.set_time_limit(0.1)  # 0.1s
        function.set_memory_limit(4 * 1024 * 1024)  # 4MB
        output_column = config["output_column"]
        for row in rows:
            output = function(row)
            if config["mode"] == "multi":
                if isinstance(output, str) and not isinstance(output, dict):
                    try:
                        output = json.loads(output)
                    except json.JSONDecodeError:
                        output = {"javascript_output": output}
                if len(pks) == 1:
                    pk_value = row[pks[0]]
                else:
                    pk_value = (row[pk] for pk in pks)

                def _update(conn):
                    sqlite_utils.Database(conn)[table].update(
                        pk_value, output, alter=True
                    )

                await db.execute_write_fn(_update)
            else:
                await db.execute_write(
                    "update [{table}] set [{output_column}] = ? where {wheres}".format(
                        table=table,
                        output_column=output_column,
                        wheres=" and ".join('"{}" = ?'.format(pk) for pk in pks),
                    ),
                    [output] + list(row[pk] for pk in pks),
                )
