import itertools
import jinja2
import os
import re
import bibi_api_gen

__device_types = {
    'ACSource': 'ac_source',
    'DCSource': 'dc_source',
    'FixedFrequency': 'fixed_frequency',
    'LeakyIntegratorAlpha': 'leaky_integrator_alpha',
    'LeakyIntegratorExp': 'leaky_integrator_exp',
    'NCSource': 'nc_source',
    'Poisson': 'poisson',
    'PopulationRate': 'population_rate',
    'SpikeRecorder': 'spike_recorder'
}
__device_properties = {
    'ACSource': 'amplitude',
    'DCSource': 'amplitude',
    'FixedFrequency': 'rate',
    'LeakyIntegratorAlpha': 'voltage',
    'LeakyIntegratorExp': 'voltage',
    'NCSource': 'mean',
    'Poisson': 'rate',
    'PopulationRate': 'rate',
    'SpikeRecorder': 'times'
}
__operator_symbols = {
    bibi_api_gen.Subtract: '({0} - {1})',
    bibi_api_gen.Add: '({0} + {1})',
    bibi_api_gen.Multiply: '{0} * {1}',
    bibi_api_gen.Divide: '{0} / {1}',
    bibi_api_gen.Min: 'min({0}, {1})',
    bibi_api_gen.Max: 'max({0}, {1})'
}


def get_default_property(device_type):
    """
    Gets the default property for the given device type

    :param device_type: The device type
    """
    return __device_properties[device_type]


def print_operator(expression):
    """
    Prints the given operator expression to a string

    :param expression: The operator expression to be printed
    """
    text = print_expression(expression.operand[0])
    operator = __operator_symbols[type(expression)]
    for i in range(1, len(expression.operand)):
        text = operator.format(text, print_expression(expression.operand[i]))
    return text


def print_expression(expression):
    """
    Prints the given flow expression to a string

    :param expression: The expression to be printed
    """

    # Pylint demands less *if* statements but each *if* is very simple so that should be ok
    # pylint: disable=R0911
    if isinstance(expression, bibi_api_gen.Scale):
        return str(expression.factor) + ' * ' + print_expression(expression.inner)
    if isinstance(expression, bibi_api_gen.Call):
        temp = expression.type + '('
        i = 1
        for argument in expression.argument:
            temp += argument.name + '=' + print_expression(argument.value_)
            if i < len(expression.argument):
                temp += ', '
            i += 1
        return temp + ')'
    if isinstance(expression, bibi_api_gen.Operator):
        return print_operator(expression)
    if isinstance(expression, bibi_api_gen.ArgumentReference):
        if expression.property_ is None:
            return expression.name
        else:
            return expression.name + '.' + expression.property_
    if isinstance(expression, bibi_api_gen.Constant):
        return str(expression.value_)

    if isinstance(expression, bibi_api_gen.SimulationStep):
        return "t"

    raise Exception('No idea how to print expression of type ' + repr(type(expression)))


def is_not_none(item):
    """
    Gets whether the given item is None (required since Jinja2 does not understand None tests)

    :param item: The item that should be tested
    :return: True if the item is not None, otherwise False
    """
    return item is not None


FOUR_SPACES = " " * 4


def print_device_config(dev):
    """
    Prints the configuration of the given device or device group

    :param dev: The device or device group
    :return: The device configuration as string
    """
    res = ""
    if dev.synapseDynamics is not None:
        res += ", synapse_dynamics=" + print_synapse_dynamics(dev.synapseDynamics)
    elif dev.synapseDynamicsRef is not None:
        res += ", synapse_dynamics=" + dev.synapseDynamicsRef.ref
    if dev.connector is not None:
        res += ", connector=" + print_connector(dev.connector)
    elif dev.connectorRef is not None:
        res += ", connector=" + dev.connectorRef.ref
    if dev.target is not None:
        res += ", receptor_type='" + dev.target.lower() + "'"
    return res


def print_synapse_dynamics(synapse_dynamics):
    """
    Creates a synapse dynamics initialization

    :param synapse_dynamics: The synanapse dynamics element
    :return: Code that creates the synapse dynamics
    """
    if isinstance(synapse_dynamics, bibi_api_gen.TsodyksMarkramMechanism):
        return "{{'type':'TsodyksMarkram', 'U':{0}, 'tau_rec':{1}, 'tau_facil':{2}}}" \
            .format(synapse_dynamics.u, synapse_dynamics.tau_rec, synapse_dynamics.tau_facil)
    raise Exception("Don't know how to print synapse dynamics of type " + str(type(synapse_dynamics)))


def print_connector(connector):
    """
    Creates a neuron connector

    :param connector: The neuron connector model
    :return: Code that creates the neuron connector
    """
    if isinstance(connector, bibi_api_gen.OneToOneConnector):
        return "{{'mode':'OneToOne', 'weights':{0}, 'delays':{1}}}".format(connector.weights, connector.delays)
    if isinstance(connector, bibi_api_gen.AllToAllConnector):
        return "{{'mode':'AllToAll', 'weights':{0}, 'delays':{1}}}".format(connector.weights, connector.delays)
    if isinstance(connector, bibi_api_gen.FixedNumberPreConnector):
        return "{{'mode':'Fixed', 'n':{2}, 'weights':{0}, 'delays':{1}}}".format(connector.weights, connector.delays,
                                                                                 connector.count)
    raise Exception("Don't know how to print connector of type " + str(type(connector)))


def __load_template(path):
    """
    Loads the template given by the specified relative path

    :param path: Template path relative to bibi configuration script (this file)
    :return: The template as Jinja2 template
    """
    template_path = os.path.join(os.path.split(__file__)[0], path)
    with open(template_path, 'r') as template_file:
        return jinja2.Template(template_file.read())


tf_template = __load_template('tf_template.pyt')


def get_referenced_dynamics(tf, config):
    """
    Gets the connectors referenced by the given transfer function

    :param tf: The given transfer function
    :return: A list of connectors
    """
    assert isinstance(tf, bibi_api_gen.BIBITransferFunction)
    assert isinstance(config, bibi_api_gen.BIBIConfiguration)
    dynamics_names = []
    for dev in itertools.chain(tf.device, tf.deviceGroup):
        if dev.synapseDynamicsRef is not None and not dev.synapseDynamicsRef.ref in dynamics_names:
            dynamics_names.append(dev.synapseDynamicsRef.ref)
    if len(dynamics_names) > 0:
        dynamics_dict = {}
        for dyn in config.synapseDynamics:
            dynamics_dict[dyn.name] = dyn
        for i in range(0, len(dynamics_names)):
            dynamics_names[i] = dynamics_dict[dynamics_names[i]]
    return dynamics_names


def get_device_name(device_type):
    """
    Gets the CLE name of the given device type

    :param device_type: The device type
    """
    return __device_types[device_type]


def __get_neurons_index(neurons, slice_format):
    """
    Gets the indexing operator for the given neuron selector

    :param neurons: The neuron selector
    :return: A string with the appropriate index or None
    """

    if isinstance(neurons, bibi_api_gen.Index):
        return str(neurons.index)
    elif isinstance(neurons, bibi_api_gen.Range):
        return slice_format(neurons.from_, neurons.step, neurons.to)
    elif isinstance(neurons, bibi_api_gen.List):
        if len(neurons.element) == 0:
            return '[]'
        neuron_list = '[' + str(neurons.element[0])
        for i in range(1, len(neurons.element)):
            neuron_list = neuron_list + ', ' + str(neurons.element[i])
        return neuron_list + ']'
    elif isinstance(neurons, bibi_api_gen.Population):
        return None
    raise Exception("Neuron Print: Don't know how to process neuron selector " + str(neurons))


def print_neurons_index(neurons):
    """
    Gets the indexing operator for the given neuron selector in a python style

    :param neurons: The neuron selector
    :return: A string with the appropriate index or None
    """

    def slice_format(from_, step, to):
        """
        Formats a slice appropriately

        :param from_: The start parameter of a slice
        :param step: The step parameter of a slice
        :param to: The stop parameter
        """
        if step is not None:
            return "slice(" + str(from_) + ", " + str(to) + ", " + str(step) + ")"
        else:
            return "slice(" + str(from_) + ", " + str(to) + ")"

    return __get_neurons_index(neurons, slice_format)


def print_neurons(neuron_selector, prefix=None):
    """
    Gets a string representing the accessed neuron population

    :param neuron_selector: The neuron selector
    :param prefix: the neuron prefix
    """
    if prefix is not None:
        index = print_neurons_index(neuron_selector)
    else:
        index = get_neurons_index(neuron_selector)
        prefix = ""
    if index is not None:
        return prefix + neuron_selector.population + "[" + index + "]"
    return prefix + neuron_selector.population


def get_referenced_connectors(tf, config):
    """
    Gets the connectors referenced by the given transfer function

    :param tf: The given transfer function
    :return: A list of connectors
    """
    connector_names = []
    for dev in itertools.chain(tf.device, tf.deviceGroup):
        if dev.connectorRef is not None and not dev.connectorRef.ref in connector_names:
            connector_names.append(dev.connectorRef.ref)
    if len(connector_names) > 0:
        conn_dict = {}
        for conn in config.connectors:
            conn_dict[conn.name] = conn
        for i in range(0, len(connector_names)):
            connector_names[i] = conn_dict[connector_names[i]]
    return connector_names

def get_tf_name(tf_code):
    """
    Returns the function name of transfer function code

    @param tf_code: string with transfer function code
    @return: function name
    """

    p = re.compile(ur'^.*def\s+(\w+)\s*\(.*', re.MULTILINE)
    ret = re.findall(p, tf_code)
    return ret[0]


def correct_indentation(text, first_line_indent_level, indent_string=FOUR_SPACES):
    """
    Adapts the indentation of the given code in order to paste it into the generated script. The
    indentation of the given text is determined based on the first content line (first line which
    consists not only of white spaces). The indentation must either use four spaces or a tab
    character.

    :param text: the original input to adapt
    :param first_line_indent_level: the target indentation level of the entire block
    :type first_line_indent_level: int
    :param indent_string: (Optional): the pattern for one level of indentation
    :return: the adapted text
    """

    text.replace("\t", indent_string)
    lines = text.split("\n")
    result = []

    first_line_indent = None
    for line in lines:
        if line.lstrip():
            if first_line_indent is None and line:
                first_line_stripped = line.lstrip()
                first_line_indent = line[:len(line) - len(first_line_stripped)]

            result.append(indent_string * first_line_indent_level + line[len(first_line_indent):])
        else:
            result.append("\n")

    return "\n".join(result)


def convert_tf(tf, bibi):
    """
    Generates the code for the given transfer function
    """
    names = dict(globals())
    names["tf"] = tf
    if isinstance(tf, bibi_api_gen.BIBITransferFunction):
        names["connectors"] = get_referenced_connectors(tf, bibi)
        names["dynamics"] = get_referenced_dynamics(tf, bibi)
    tf_source = tf_template.render(names)
    if not hasattr(tf, 'name'):
        tf.name = get_tf_name(tf_source)

    if isinstance(tf, bibi_api_gen.PythonTransferFunction):
        importedLine = "    # Imported Python Transfer Function"
        if importedLine not in tf_source:
            tf_source = importedLine + tf_source

    return ''.join(l for l in tf_source.splitlines(True) if not l.isspace())
