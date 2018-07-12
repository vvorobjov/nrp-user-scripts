"""
Migrate experiments with XML defined tranfer functions

Usage:
    pyton migrate_xml_tfs.py <bibi_file_path>
"""

__author__ = 'Claudio Sousa'
import sys
import xml.dom.minidom
from lib import bibi_api_gen, convert_tf, correct_indentation
import os

bibi_file = sys.argv[1]
print "Checking", bibi_file

with open(bibi_file) as b_file:
    bibi = bibi_api_gen.CreateFromDocument(b_file.read())

found_xml_tf = False
dirname = os.path.dirname(bibi_file)
tfs_to_remove = []
for tf in bibi.transferFunction:
    if isinstance(tf, bibi_api_gen.PythonTransferFunction) and tf.src:
        continue
    tf_src = convert_tf(tf, bibi)
    tf_src = correct_indentation(tf_src, 0)
    python_tf_node = bibi_api_gen.PythonTransferFunction()
    tfs_to_remove.append(tf)
    python_tf_node.src = tf.name + ".py"
    bibi.transferFunction.append(python_tf_node)

    found_xml_tf = True
    tf_file = os.path.join(dirname, python_tf_node.src)
    print "\tCreating tf file", tf_file
    with open(tf_file, 'w') as py_file:
        py_file.write(tf_src)

if found_xml_tf:
    for tf in tfs_to_remove:
        bibi.transferFunction.remove(tf)

    print "\tUpdating bibi", bibi_file
    new_bibi = xml.dom.minidom.parseString(bibi.toxml("utf-8")).toprettyxml()
    with open(bibi_file, 'w') as b_file:
        b_file.write(new_bibi)
