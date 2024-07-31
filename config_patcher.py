import re
from pathlib import Path
import click
import toml
import json

import yaml

def flatten_values(sections, values):
    result = []
    if type(values) == dict:
        for key, value in values.items():
            if type(value) == dict:
                result.extend(flatten_values(sections + [key], value))
            else:
                result.append((sections + [key], value))
    else:
        result.append((sections, values))
    return result

section_matcher = re.compile(r"^\s*(\w+)\s+\{\s*$")
end_section = re.compile(r"^\s*\}\s*$")

@click.command()
@click.option("--dry-run", is_flag=True, default=False)
@click.argument("config_file", type=click.File('r'))
@click.argument("config_dir", type=click.Path(exists=True, file_okay=False))
def patch(config_file, config_dir, dry_run):
    if config_file.name.endswith(".toml"):
        spec = toml.load(config_file)
    elif config_file.name.endswith(".json"):
        spec = json.load(config_file)
    elif config_file.name.endswith(".yaml"):
        spec = yaml.load(config_file)
    else:
        raise ValueError("Unsupported config file format. Supported: toml, json, yaml")
    
    config_dir = Path(config_dir)

    for dest_file, sections in spec.items():
        file = config_dir / dest_file
        if not file.exists() and config_dir.name == "config":
            # some files aren't in the config directory
            file = config_dir.parent / dest_file

        if not file.exists():
            print(f"file {file} does not exist")
            continue

        with open(file, "r+") as f:
            lines = f.readlines()

            flat = flatten_values([], sections)

            changed = False
            for path, value in flat:
                if type(value) == bool:
                    # Don't use python casing for booleans
                    value = str(value).lower()
                elif type(value) == str:
                    # Wrap strings in quotes
                    value = f'"{value}"'
                # TODO handle other values like lists, objects, etc
                key = path.pop()

                matcher = re.compile(rf"^(\s*{key}\s*=\s*)")
                current_section = []
                for i, line in enumerate(lines):
                    line_section = section_matcher.match(line)
                    if line_section:
                        current_section.append(line_section.group(1))
                        continue
                    
                    if end_section.match(line):
                        current_section.pop()
                        continue

                    if current_section != path:
                        continue

                    m = matcher.match(line)
                    if m:
                        new_line = f"{m.group(1)}{value}\n"
                        if lines[i] != new_line:
                            print(f"patching {file.name}:{i+1}:\n-{line}+{lines[i]}")
                            lines[i] = new_line
                            changed = True
                        break
            
            if changed and not dry_run:
                f.seek(0)
                f.truncate(0)
                f.writelines(lines)
                print(f"updated {file}")
            if not changed:
                print(f"{file} up to date")


if __name__ == "__main__":
    patch()
