# ==============================================
# Automated System-wide Strength Evaluation Tool (ASSET) - EET Based Sensitivity Analysis
# Contributors: Pranav Sharma, Shahil Shah
# Last modified: 08/21/26
# Pranav Sharma and Shahil Shah, "Sizing and Placement of Grid Strengthening Devices Using Extra Element 
# Theorem," in IEEE Open Access Journal of Power and Energy, Sep. 2026, doi: 10.1109/OAJPE.2026.3732363.
# Pranav Sharma, Shahil Shah, "Application of the Extra Element Theorem
# for Grid Strength Analysis in IBR-Dominated Systems", IEEE PES General Meeting, Jul. 2025.

# ==============================================
# Copyright (c) 2026 Alliance for Energy Innovation, LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# ==============================================

import os
import sys
sys.path.append(r"C:\Program Files (x86)\PTI\PSSE34\PSSBIN")  # Update as per your version
os.environ['PATH'] += r";C:\Program Files (x86)\PTI\PSSE34\PSSBIN"
import numpy as np
import pandas as pd


# =============================================================================================
# Set PSS/E installation folder
# Remark: change to match the required PSS/E version
# =============================================================================================
# If the users know the exact installation folder, they can directly set it up:
pssbindir = r"C:\Program Files (x86)\PTI\PSSE34\PSSBIN"
pssepydir = r"""C:\Program Files (x86)\PTI\PSSE34\PSSPY27"""

# If the users do not know the installation folder, they can use pssepath package for auto-setup
# package pssepath: https://pypi.org/project/pssepath/
#import pssepath
#pssepath.add_pssepath()

# =============================================================================================
# Load and initialize PSS/E API
# Remark: change to match the required PSS/E version
# =============================================================================================
import psse34
import psspy,excelpy,dyntools,redirect,pssarrays

from psspy import _i
from psspy import _f
from psspy import _s
redirect.psse2py()
# =============================================================================================


working_dir = os.getcwd()




def SC_k_lvl(psspy, busN, k, all_POIs, Z9999_flag, machine_id="1"):
	"""Run IEC short-circuit at one bus and return parsed SCC values/branch terms."""
	tmp_dir = working_dir+"\\temp"
	sc_k_0 = None
	SCC_kl = []

	def _machine_exists(target_bus, target_id):
		"""Return True only when the requested machine record exists at bus."""
		for fn_name in ("macdat", "machdat"):
			fn = getattr(psspy, fn_name, None)
			if fn is None:
				continue
			for field in ("MBASE", "P"):
				try:
					ierr, _ = fn(int(target_bus), target_id, field)
					if ierr == 0:
						return True
				except Exception:
					continue
		return False

	# Run SC analysis
	# Set equivalent high-impedance contribution for target machine ID.
	if Z9999_flag == 1:
		if _machine_exists(busN, machine_id):
			psspy.machine_chng_2(busN, machine_id, [psspy._i, psspy._i, psspy._i,
											psspy._i, psspy._i, psspy._i],
						 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, 9999.0,
						  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f])
	else:
		for busi in all_POIs:
			if _machine_exists(busi, machine_id):
				psspy.machine_chng_2(busi, machine_id, [psspy._i, psspy._i, psspy._i,
											psspy._i, psspy._i, psspy._i],
							 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
							  9999.0, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
							  psspy._f])

	psspy.short_circuit_coordinates(1)
	ierr = psspy.short_circuit_units(ival=1)
	psspy.progress_output(6,"",[0,0])
	psspy.bsys(1, 0, [0.0, 0.0], 0, [], 2, [busN], 0, [], 0, [])
	# psspy.iecs_4(1, 0, [1, 0, 0, 0, 3, 3, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0], [0.08333, 1.1], "", "", "")

	temp = sys.stdout	# store original stdout object for later

	sys.stdout = open(tmp_dir+"\\POI_" + str(busN) + "_lvl_" + str(k) + ".txt","w")
	sid = 1
	all = 0

	flt3ph = 1
	fltlg = 0
	fltllg = 0
	fltll = 0
	rptop = 3

	# k
	fltloc = 0
	linout = 0
	linend = 0
	tpunty = 0

	lnchrg = 1
	shntop = 1
	dcload = 0
	zcorec = 0
	cfactor = 0 # optnftrc in iecs_current()

	loadop = 1 # originally 0
	genxop = 0


	brktime = 0.08333
	psspy.iecs_4(sid, all, [flt3ph, fltlg, fltllg, fltll, rptop, k, fltloc, linout, linend, tpunty, lnchrg, shntop, dcload, zcorec, cfactor, loadop, genxop], [brktime, 1.1], "", "", "")
	sys.stdout.close()

	sys.stdout = temp	# restore print commands to interactive prompt

	f = open(tmp_dir+"\\POI_" + str(busN) + "_lvl_" + str(k) + ".txt",'r')
	# f = open('POI_126287_lvl_3.txt', 'r')
	alllines = f.readlines()
	size = len(alllines)
	i = 0
	strbus = ' X------------ BUS ------------X '
	strbus_len = len(strbus)
	stratbus = ' AT BUS'
	stratbus_len = len(stratbus)
	strfrom = ' X----------- FROM ------------X '
	strfrom_len = len(strfrom)
	strend = ' --------------------------------------'
	strend_len = len(strend)
	str3PH = '3PH'
	sc_k = []
	while i <= size-1:
		aa = alllines[i]
		size_aa = len(aa)
		if size_aa > strbus_len and aa[0:strbus_len] == strbus:
			bb = alllines[i+1]
			cc = bb.split()
			ind = cc.index(str3PH)
			c_mag = cc[ind+1]
			c_ang = cc[ind+2]
			bus_num = cc[0]
			bus_ind = int(bus_num)
			sc_mag = float(c_mag)
			if c_ang.find('-') == -1:
				ind_minus = None
			else:
				ind_minus = c_ang.index('-')
			if ind_minus != None:
				if ind_minus>1:
					c_ang = c_ang[0:ind_minus-1]
			sc_ang = float(c_ang)
			sc_k_0 = np.array([bus_ind,sc_mag])
		if size_aa > stratbus_len and aa[0:stratbus_len] == stratbus:  # go to AT BUS
			bb = alllines[i]
			cc = bb.split()
			ind = 2
			bus_to = cc[ind]
			bus_to_ind = int(bus_to)
		if size_aa > strfrom_len and aa[0:strfrom_len] == strfrom:
			checkedallfrombus = 0
			i = i + 1
			while checkedallfrombus == 0:
				bb = alllines[i]
				if len(bb)>strend_len and bb[0:strend_len] == strend:
					checkedallfrombus = 1
					continue
				else:
					cc = bb.split()
					bus_from = cc[0]
					flag = bus_from.isdigit()
					if len(cc)>1 and flag:
						ind = bb.find(']')
						cc = bb[ind + 1:].split()
						line_id = cc[1]
						ele_cc = cc[3]
						if ele_cc.find('-') == -1:
							ind_minus = None
						else:
							ind_minus = ele_cc.index('-')
						if ind_minus != None:
							if ind_minus > 1:
								ele_cc = ele_cc[0:ind_minus - 1]
						ele_sc = float(ele_cc)
						if int(bus_from)<=int(bus_to): # make sure the same branch is only included once
							SCC_kl.append([int(bus_from), int(bus_to), line_id, ele_sc])
				i = i + 1
		i = i + 1

	leng = len(SCC_kl)
	SCC_kl_array = np.zeros([leng, 3])
	for i in range(leng):
		SCC_kl_array[i][0] = float(SCC_kl[i][0])
		SCC_kl_array[i][1] = float(SCC_kl[i][1])
		SCC_kl_array[i][2] = float(SCC_kl[i][3])
		pass
	if sc_k_0 is None:
		raise ValueError("No short-circuit result was parsed for POI bus %d at k=%s." % (busN, k))
	return sc_k_0, SCC_kl, SCC_kl_array


def IdTop2Brch(PFcase, busNlimit, SCC_kl, SCC_kl_array, SCC_ranking):
	"""Identify two strongest non-islanding branches for N-1/N-2 screening."""
	tp1 = []
	tp2 = []
	for i in range(len(SCC_ranking)):
		psspy.psseinit(busNlimit)
		psspy.case(PFcase)

		Line_RX = np.asarray(psspy.abrncplx(-1, 1, 1, 1, 1, ['RX'])[1][0])
		Line_chg = np.asarray(psspy.abrnreal(-1, 1, 1, 1, 1, ['CHARGING'])[1][0])
		Line_from = np.asarray(psspy.abrnint(-1, 1, 1, 1, 1, ['FROMNUMBER'])[1][0])
		Line_to = np.asarray(psspy.abrnint(-1, 1, 1, 1, 1, ['TONUMBER'])[1][0])
		Line_id = psspy.abrnchar(-1, 0, 0, 1, 1, ['ID'])[1][0]


		if tp1:
			ierr = psspy.branch_chng_3(int(SCC_kl_array[tp1[0]][0]), int(SCC_kl_array[tp1[0]][1]),
								SCC_kl[tp1[0]][2], [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i],
								[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								 psspy._f, psspy._f, psspy._f, psspy._f],
								[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								 psspy._f, psspy._f, psspy._f, psspy._f], "")
			if ierr != 0:
				psspy.two_winding_chng_5(int(SCC_kl_array[tp1[0]][0]), int(SCC_kl_array[tp1[0]][1]),
										 SCC_kl[tp1[0]][2], [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i,
										  psspy._i, psspy._i, psspy._i, 0, psspy._i, psspy._i, psspy._i],
										 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
										  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
										  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f],
										 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
										  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f], "", "")

		ierr = psspy.branch_chng_3(int(SCC_kl_array[SCC_ranking[i]][0]), int(SCC_kl_array[SCC_ranking[i]][1]),
							SCC_kl[SCC_ranking[i]][2], [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i],
							[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
							 psspy._f, psspy._f, psspy._f, psspy._f],
							[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
							 psspy._f, psspy._f, psspy._f, psspy._f], "")
		if ierr != 0:
			psspy.two_winding_chng_5(int(SCC_kl_array[SCC_ranking[i]][0]), int(SCC_kl_array[SCC_ranking[i]][1]),
							SCC_kl[SCC_ranking[i]][2], [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i,
									  psspy._i, psspy._i, psspy._i, 0, psspy._i, psspy._i, psspy._i],
									 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
									  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
									  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f],
									 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
									  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f], "", "")

		ierr, buses = psspy.tree(1, -1)  # len(buses)=0 if there is no island, otherwise there is island
		psspy.tree(2, -1)  # need to call tree for 2nd time as required by this API, so program can move on

		if buses == 0:
			if not tp1:
				if not tp2:
					temp1 = np.absolute(Line_from - int(SCC_kl_array[SCC_ranking[i]][1])) + np.absolute(
						Line_to - int(SCC_kl_array[SCC_ranking[i]][0]))
					temp2 = np.absolute(Line_from - int(SCC_kl_array[SCC_ranking[i]][0])) + np.absolute(
						Line_to - int(SCC_kl_array[SCC_ranking[i]][1]))
					temp3 = np.multiply(np.sign(temp1), np.sign(temp2))
					idx = np.argmin(temp3)
					Z = np.absolute(Line_RX[idx])
					if Z > 1e-4:
						tp1.append(SCC_ranking[i])
			elif tp1:
				if tp2:
					break

				temp1 = np.absolute(Line_from - int(SCC_kl_array[SCC_ranking[i]][1])) + np.absolute(
					Line_to - int(SCC_kl_array[SCC_ranking[i]][0]))
				temp2 = np.absolute(Line_from - int(SCC_kl_array[SCC_ranking[i]][0])) + np.absolute(
					Line_to - int(SCC_kl_array[SCC_ranking[i]][1]))
				temp3 = np.multiply(np.sign(temp1), np.sign(temp2))
				idx = np.argmin(temp3)
				Z = np.absolute(Line_RX[idx])
				# if Z > 0.005:
				if Z > 1e-4:
					tp2.append(SCC_ranking[i])
				else:
					continue
	return tp1, tp2



def CalcSccN12(PFcase, busNlimit, POIi, SCC_kl, SCC_kl_array, tp1, tp2, all_POIs, Z9999_flag, machine_id="1"):
	"""Compute POI short-circuit strength under selected N-1 and N-2 outages."""
	# SCC at N-1
	psspy.psseinit(busNlimit)
	psspy.case(PFcase)
	psspy.short_circuit_coordinates(1)
	ierr = psspy.short_circuit_units(ival=1)
	psspy.progress_output(6,"",[0,0])

	ierr = psspy.branch_chng_3(int(SCC_kl_array[tp1[0]][0]), int(SCC_kl_array[tp1[0]][1]),
						SCC_kl[tp1[0]][2], [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i],
						[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
						 psspy._f, psspy._f, psspy._f, psspy._f],
						[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
						 psspy._f, psspy._f, psspy._f, psspy._f], "")
	if ierr!=0:
		psspy.two_winding_chng_5(int(SCC_kl_array[tp1[0]][0]), int(SCC_kl_array[tp1[0]][1]),
						SCC_kl[tp1[0]][2],
								 [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i,
								  psspy._i, psspy._i, 0, psspy._i, psspy._i, psspy._i],
								 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f],
								 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								  psspy._f, psspy._f, psspy._f, psspy._f], "", "")
	SCC_POIi_N1, temp, temp = SC_k_lvl(psspy, POIi, 0, all_POIs, Z9999_flag, machine_id)

	# SCC at N-2
	psspy.short_circuit_coordinates(1)
	psspy.psseinit(busNlimit)
	psspy.case(PFcase)
	psspy.short_circuit_coordinates(1)
	ierr = psspy.short_circuit_units(ival=1)
	psspy.progress_output(6,"",[0,0])
	ierr = psspy.branch_chng_3(int(SCC_kl_array[tp1[0]][0]), int(SCC_kl_array[tp1[0]][1]),
						SCC_kl[tp1[0]][2], [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i],
						[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
						 psspy._f, psspy._f, psspy._f, psspy._f],
						[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
						 psspy._f, psspy._f, psspy._f, psspy._f], "")
	if ierr!=0:
		psspy.two_winding_chng_5(int(SCC_kl_array[tp1[0]][0]), int(SCC_kl_array[tp1[0]][1]),
						SCC_kl[tp1[0]][2],
								 [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i,
								  psspy._i, psspy._i, 0, psspy._i, psspy._i, psspy._i],
								 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f],
								 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								  psspy._f, psspy._f, psspy._f, psspy._f], "", "")

	ierr = psspy.branch_chng_3(int(SCC_kl_array[tp2[0]][0]), int(SCC_kl_array[tp2[0]][1]),
						SCC_kl[tp2[0]][2], [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i],
						[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
						 psspy._f, psspy._f, psspy._f, psspy._f],
						[psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
						 psspy._f, psspy._f, psspy._f, psspy._f], "")
	if ierr!=0:
		psspy.two_winding_chng_5(int(SCC_kl_array[tp2[0]][0]), int(SCC_kl_array[tp2[0]][1]),
						SCC_kl[tp2[0]][2],
								 [0, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i, psspy._i,
								  psspy._i, psspy._i, 0, psspy._i, psspy._i, psspy._i],
								 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								  psspy._f, psspy._f, psspy._f, psspy._f, psspy._f],
								 [psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f, psspy._f,
								  psspy._f, psspy._f, psspy._f, psspy._f], "", "")

	SCC_POIi_N2, temp, temp = SC_k_lvl(psspy, POIi, 0, all_POIs, Z9999_flag, machine_id)
	return SCC_POIi_N1[1], SCC_POIi_N2[1]


def _eet_get_bus_type(psspy_api, bus_number):
	for getter_name in ("busdat", "busint"):
		getter = getattr(psspy_api, getter_name, None)
		if getter is None:
			continue
		try:
			ierr, bus_type = getter(int(bus_number), 'TYPE')
			if ierr == 0:
				return int(bus_type)
		except Exception:
			continue
	return None


def _eet_validate_input_buses(psspy_api, poi_list, candidate_list):
	missing_poi = []
	missing_candidate = []

	for bus_number in poi_list:
		if _eet_get_bus_type(psspy_api, bus_number) is None:
			missing_poi.append(int(bus_number))

	for bus_number in candidate_list:
		if _eet_get_bus_type(psspy_api, bus_number) is None:
			missing_candidate.append(int(bus_number))

	if missing_poi or missing_candidate:
		message_lines = [
			"Loaded case does not contain all requested POI/candidate buses.",
			"Check that the .sav file and the POI/candidate CSV files belong to the same network model.",
		]
		if missing_poi:
			message_lines.append("Missing POI buses: %s" % ", ".join(str(b) for b in missing_poi))
		if missing_candidate:
			message_lines.append("Missing candidate buses: %s" % ", ".join(str(b) for b in missing_candidate))
		raise ValueError("\n".join(message_lines))


def _eet_init_case(psspy_api, PFcase, busNlimit):
	psspy_api.psseinit(busNlimit)
	psspy_api.progress_output(6, "", [0, 0])
	psspy_api.alert_output(6, "", [0, 0])
	psspy_api.prompt_output(6, "", [0, 0])
	ierr = psspy_api.case(PFcase)
	if ierr != 0:
		raise Exception("SAV file cannot be opened.")


def _eet_add_candidate_generator(psspy_api, bus_number, Gm, xsource, machine_id_options):
	bus_type = _eet_get_bus_type(psspy_api, bus_number)
	if bus_type is None:
		print("Skipping candidate bus %d: unable to read bus type." % int(bus_number))
		return None

	if bus_type == 4:
		print("Skipping candidate bus %d: offline bus (type 4) is not compatible." % int(bus_number))
		return None

	if bus_type not in [1, 2, 3]:
		print("Skipping candidate bus %d: bus type %d is not compatible." % (int(bus_number), bus_type))
		return None

	bus_converted_from_load = False

	if bus_type == 1:
		ierr = psspy_api.bus_chng_4(int(bus_number), 0, [2, _i, _i, _i], [_f, _f, _f, _f, _f, _f, _f], _s)
		if ierr != 0:
			print("Skipping candidate bus %d: failed to convert load bus to generator bus." % int(bus_number))
			return None
		bus_converted_from_load = True

	psspy_api.plant_data_4(int(bus_number), 0, [0, 0], [1.0, 100.0])

	add_errors = []
	for machine_id in machine_id_options:
		ierr = psspy_api.machine_data_2(
			int(bus_number),
			machine_id,
			[_i, _i, _i, _i, _i, _i],
			[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, Gm]
		)
		if ierr != 0:
			add_errors.append("machine_data_2(ID=%s,ierr=%d)" % (machine_id, ierr))
			continue

		ierr = psspy_api.machine_chng_2(
			int(bus_number),
			machine_id,
			[_i, _i, _i, _i, _i, _i],
			[_f, _f, _f, _f, 0.0, 0.0, Gm, _f, xsource, _f, _f, _f, _f, _f, _f, _f, _f]
		)
		if ierr == 0:
			return machine_id, bus_converted_from_load

		add_errors.append("machine_chng_2(ID=%s,ierr=%d)" % (machine_id, ierr))
		try:
			psspy_api.purgmac(int(bus_number), machine_id)
		except Exception:
			pass

	if len(add_errors) > 0:
		print("Skipping candidate bus %d: failed to add ET/XE dummy machine (%s)." %
			  (int(bus_number), "; ".join(add_errors)))
	else:
		print("Skipping candidate bus %d: no free machine ID available from ET/XE." % int(bus_number))
	return None


def _eet_remove_candidate_generator(psspy_api, bus_number, machine_id, bus_converted_from_load):
	try:
		psspy_api.purgmac(int(bus_number), machine_id)
	except Exception:
		pass

	if bus_converted_from_load:
		try:
			psspy_api.bus_chng_4(int(bus_number), 0, [1, _i, _i, _i], [_f, _f, _f, _f, _f, _f, _f], _s)
		except Exception:
			pass


def _eet_sanitize_extra_element_params(Gm, xsource):
	"""Return numerically safe values for the synthetic extra element.

	Very large Gm can trigger floating-point errors in some PSSE cases.
	"""
	try:
		gm_val = float(Gm)
	except Exception:
		gm_val = 10000.0

	try:
		x_val = float(xsource)
	except Exception:
		x_val = 1.0

	if not np.isfinite(gm_val) or gm_val <= 0.0:
		gm_val = 10000.0
	if not np.isfinite(x_val) or x_val <= 0.0:
		x_val = 1.0

	# Practical cap to avoid PSSE numerical overflow while preserving EET behavior.
	gm_cap = 10000.0
	if gm_val > gm_cap:
		print("Warning: Gm=%.3f is large; using %.1f for numerical stability." % (gm_val, gm_cap))
		gm_val = gm_cap

	return gm_val, x_val


def _eet_build_matrix(entry_list, row_ids, col_ids):
	row_map = {int(rid): idx for idx, rid in enumerate(row_ids)}
	col_map = {int(cid): idx for idx, cid in enumerate(col_ids)}

	mat = np.full((len(row_ids), len(col_ids)), np.nan)
	for entry in entry_list:
		c_bus = int(entry[0])
		p_bus = int(entry[1])
		val = float(entry[2])
		if p_bus in row_map and c_bus in col_map:
			mat[row_map[p_bus], col_map[c_bus]] = val
	return mat


def _eet_compute_sensitivity_from_rows(s_i0_rows, s_k0_rows, s_ki_rows):
	poi_ids = [int(v[0]) for v in s_i0_rows]
	cand_ids = [int(v[0]) for v in s_k0_rows]
	sk0_map = {int(v[0]): float(v[1]) for v in s_k0_rows}

	ski_mat = _eet_build_matrix(s_ki_rows, poi_ids, cand_ids)
	sens_mat = np.full_like(ski_mat, np.nan)

	for i, poi_bus in enumerate(poi_ids):
		for k, cand_bus in enumerate(cand_ids):
			sk0 = sk0_map[cand_bus]
			ski = ski_mat[i, k]
			if np.isnan(ski) or abs(ski) < 1e-9:
				sens_val = np.nan
			elif poi_bus == cand_bus:
				sens_val = 1.0
			else:
				sens_val = abs(1.0 - (sk0 / ski))
			sens_mat[i, k] = sens_val

	return poi_ids, cand_ids, sens_mat


def _eet_compute_gamma_from_rows(s_k0_rows, s_ki_rows, poi_ids, cand_ids):
	"""Compute gamma_{k,i} = S_{k,i}/S_k - 1 with matrix shape [POI, Candidate]."""
	sk0_map = {int(v[0]): float(v[1]) for v in s_k0_rows}
	ski_mat = _eet_build_matrix(s_ki_rows, poi_ids, cand_ids)
	gamma_mat = np.full_like(ski_mat, np.nan)

	eps = 1e-9
	for i in range(len(poi_ids)):
		for k, cand_bus in enumerate(cand_ids):
			sk = sk0_map.get(int(cand_bus), np.nan)
			ski = ski_mat[i, k]

			if np.isnan(sk) or abs(sk) < eps or np.isnan(ski):
				gamma = np.nan
			elif np.isposinf(ski):
				gamma = np.inf
			elif np.isneginf(ski):
				gamma = np.nan
			else:
				gamma = (ski / sk) - 1.0
				if gamma < 0.0 and gamma > -1e-8:
					gamma = 0.0

			gamma_mat[i, k] = gamma

	return gamma_mat


def EET_compute(psspy_api, PFcase, poi_list, candidate_list, busNlimit=50,
				Z9999_flag=1, K=10, Gm=100000.0, xsource=1.0,
				sc_machine_id="1", base_dir=None):
	"""Compute EET outputs for S_i0, S_k0, S_ki and sensitivity.

	Returns a dict with row-wise outputs and sensitivity matrix components.
	"""
	global working_dir
	if base_dir is not None:
		working_dir = base_dir

	machine_id_options = ("ET", "XE", "E", "X")
	gm_eff, xsource_eff = _eet_sanitize_extra_element_params(Gm, xsource)

	_eet_init_case(psspy_api, PFcase, busNlimit)
	_eet_validate_input_buses(psspy_api, poi_list, candidate_list)

	s_i0_rows = []
	s_k0_rows = []
	s_i_given_g_rows = []
	s_ki_rows = []

	print("Computing S_i0 (base SCMVA at POIs)...")
	for i, poi_bus in enumerate(poi_list):
		print("Processing POI %d/%d" % (i + 1, len(poi_list)))
		_eet_init_case(psspy_api, PFcase, busNlimit)
		try:
			SCC_POI, _, _ = SC_k_lvl(psspy_api, poi_bus, K, poi_list, Z9999_flag, machine_id=sc_machine_id)
		except ValueError as exc:
			print("Skipping POI %d: %s" % (poi_bus, exc))
			continue
		s_i0_rows.append([int(SCC_POI[0]), float(SCC_POI[1])])

	print("Computing S_k0 (base SCMVA at candidate buses)...")
	for k_idx, cand_bus in enumerate(candidate_list):
		print("Processing candidate %d/%d" % (k_idx + 1, len(candidate_list)))
		_eet_init_case(psspy_api, PFcase, busNlimit)
		try:
			SCC_Candidate, _, _ = SC_k_lvl(psspy_api, cand_bus, K, candidate_list, Z9999_flag, machine_id=sc_machine_id)
		except ValueError as exc:
			print("Skipping candidate bus %d: %s" % (cand_bus, exc))
			continue
		s_k0_rows.append([int(SCC_Candidate[0]), float(SCC_Candidate[1])])

	s_i0_map = {int(row[0]): float(row[1]) for row in s_i0_rows}
	s_k0_map = {int(row[0]): float(row[1]) for row in s_k0_rows}

	print("Computing impact of extra element connected at candidate bus on each of the POIs...")
	for k_idx, cand_bus in enumerate(candidate_list):
		print("Processing candidate %d/%d" % (k_idx + 1, len(candidate_list)))
		_eet_init_case(psspy_api, PFcase, busNlimit)

		candidate_setup = _eet_add_candidate_generator(psspy_api, cand_bus, gm_eff, xsource_eff, machine_id_options)
		if candidate_setup is None:
			continue
		machine_id_added, bus_converted_from_load = candidate_setup

		try:
			for poi_bus in poi_list:
				try:
					SCC_POI_g, _, _ = SC_k_lvl(psspy_api, poi_bus, K, poi_list, Z9999_flag, machine_id=sc_machine_id)
				except ValueError as exc:
					print("Skipping POI %d for candidate %d: %s" % (int(poi_bus), int(cand_bus), exc))
					continue

				s_i_given_g = float(SCC_POI_g[1])
				s_i_given_g_rows.append([int(cand_bus), int(SCC_POI_g[0]), s_i_given_g])

				s_i0 = s_i0_map.get(int(poi_bus))
				s_k0 = s_k0_map.get(int(cand_bus))
				if s_i0 is None or s_k0 is None:
					continue

				denominator = (s_i0 * s_k0) + (gm_eff * s_i0) - (s_i_given_g * s_k0)
				if abs(denominator) < 1e-9:
					s_ki = np.nan
				else:
					s_ki = (gm_eff * s_i_given_g * s_k0) / denominator

				s_ki_rows.append([int(cand_bus), int(SCC_POI_g[0]), s_ki])
		finally:
			_eet_remove_candidate_generator(psspy_api, cand_bus, machine_id_added, bus_converted_from_load)

	poi_ids, cand_ids, sens_mat = _eet_compute_sensitivity_from_rows(s_i0_rows, s_k0_rows, s_ki_rows)
	gamma_mat = _eet_compute_gamma_from_rows(s_k0_rows, s_ki_rows, poi_ids, cand_ids)

	return {
		's_i0_rows': s_i0_rows,
		's_k0_rows': s_k0_rows,
		's_i_given_g_rows': s_i_given_g_rows,
		's_ki_rows': s_ki_rows,
		'poi_ids': poi_ids,
		'cand_ids': cand_ids,
		'sens_mat': sens_mat,
		'gamma_mat': gamma_mat,
	}