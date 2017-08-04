#!/usr/bin/env python
import dynaphopy.interface.iofile as iofile
import dynaphopy.interface.phonopy_link as phonopy_link

import numpy as np
import yaml
import argparse
import glob

from phonopy import PhonopyQHA

parser = argparse.ArgumentParser(description='thermal_extractor options')
parser.add_argument('input_file', metavar='data_file', type=str,
                    help='input file containing structure related data')

parser.add_argument('-fc', metavar='data_file', type=str, nargs='*',
                    help='phonopy force constant files')

parser.add_argument('-tp', metavar='data_file', type=str, nargs='*',
                    help='phonopy thermal properties files')

parser.add_argument('-ev', metavar='data', type=str,
                    help='Energy volume file')

parser.add_argument('-t', metavar='F', type=float, default=300,
                    help='define custom supercell')

parser.add_argument('-p', action='store_true',
                    help='Plot QHA data')

args = parser.parse_args()

# Read energy volume data
target_temperature = args.t
ev_file = np.loadtxt(args.ev)
volumes = ev_file.T[0]
electronic_energies = ev_file.T[1]

# Read force constants
fc_filenames = []
for i in args.fc:
    fc_filenames += list(sorted(glob.iglob(i)))

# Read and setup thermal_properties
tp_filenames = []
for i in args.tp:
    tp_filenames += list(sorted(glob.iglob(i)))

temperatures = []
fe_phonon = []
entropy = []
cv = []

for filename in tp_filenames:
    temperatures = []
    entropy_i = []
    fe_i = []
    cv_i = []

    with open(filename, 'r') as stream:
        thermal_properties = dict(yaml.load(stream))
        for tp in thermal_properties['thermal_properties']:
            temperatures.append(tp['temperature'])
            entropy_i.append(tp['entropy'])
            fe_i.append(tp['free_energy'])
            cv_i.append(tp['heat_capacity'])

    fe_phonon.append(fe_i)
    entropy.append(entropy_i)
    cv.append(cv_i)

sort_index = np.argsort(volumes)

volumes = np.array(volumes)[sort_index]
electronic_energies = np.array(electronic_energies)[sort_index]
temperatures = np.array(temperatures)
fe_phonon = np.array(fe_phonon).T[:, sort_index]
entropy = np.array(entropy).T[:, sort_index]
cv = np.array(cv).T[:, sort_index]

# Apply QHA using phonopy
phonopy_qha = PhonopyQHA(np.array(volumes),
                         np.array(electronic_energies),
                         eos="vinet",
                         temperatures=np.array(temperatures),
                         free_energy=np.array(fe_phonon),
                         cv=np.array(cv),
                         entropy=np.array(entropy),
                         #t_max=target_temperature,
                         verbose=False)

if args.p:
    phonopy_qha.plot_qha().show()

volume_temperature = phonopy_qha.get_volume_temperature()
qha_temperatures = phonopy_qha._qha._temperatures[:phonopy_qha._qha._max_t_index]
# helmholtz_volume = phonopy_qha.get_helmholtz_volume()
# thermal_expansion = phonopy_qha.get_thermal_expansion()
# heat_capacity_P_numerical = phonopy_qha.get_heat_capacity_P_numerical()
# volume_expansion = phonopy_qha.get_volume_expansion()
# gibbs_temperature = phonopy_qha.get_gibbs_temperature()

# Fit force constants as a function of the temperature
from scipy.interpolate import interp1d

fit_vt = interp1d(qha_temperatures, volume_temperature, kind='quadratic')
target_volume = fit_vt(target_temperature)


input_parameters = iofile.read_parameters_from_input_file(args.input_file)

if 'structure_file_name_outcar' in input_parameters:
    structure = iofile.read_from_file_structure_outcar(input_parameters['structure_file_name_outcar'])
else:
    structure = iofile.read_from_file_structure_poscar(input_parameters['structure_file_name_poscar'])
structure.get_data_from_dict(input_parameters)

fc_supercell = input_parameters['supercell_phonon']

force_constants_mat = []
for filename in fc_filenames:
    force_constants = phonopy_link.get_force_constants_from_file(filename, fc_supercell=fc_supercell)
    force_constants_mat.append(force_constants.get_array())

force_constants_mat = np.array(force_constants_mat).T
f_temperature = interp1d(volumes, force_constants_mat, kind='quadratic')

# Get force constants at the requested temperature
target_fc = f_temperature(target_volume).T

phonopy_link.write_FORCE_CONSTANTS(target_fc,filename='FORCE_CONSTANTS_TEST')

print ('QHA Renormalized force constants written in file')
