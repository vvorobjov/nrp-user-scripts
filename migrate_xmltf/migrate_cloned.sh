#!/usr/bin/env bash

. ~/.opt/platform_venv/bin/activate

#find $HBP/Experiments -type f -iname  "*.bibi" -exec python $HBP/user-scripts/migrate_xmltf/migrate_xml_tfs.py {} \;
find ~/.opt/nrpStorage -type f -iname  "*.bibi" -exec python $HBP/user-scripts/migrate_xmltf/migrate_xml_tfs.py {} \;