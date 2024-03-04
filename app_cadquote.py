from flask import Flask, render_template, request, jsonify
import pandas as pd

app = Flask(__name__)

# cadweld data containing cable dimmensions, V/M info
def get_min_max_data():
    data_min_max = pd.read_csv("cad_quote_simple.csv")
    # rename the columns for better understanding
    data_min_max.columns = ['Part','PC_code', 'PC_dia', 'SC_code', 'SC_dia', 'Same','Cond_avg','P_desc','S_desc','WM','Plus','Drop']
    # Generate the Plus_Num column which will contain all the W/M numbers and convert it into int
    data_min_max['Plus_Num'] = data_min_max['Plus'].str.extract('(\d+)').astype(int)
    # Delete garbage
    data_min_max = data_min_max.drop(columns='Drop')
    return (data_min_max)

# pivot table containing min and max values - grouped by WM where cables are identical
def get_min_max_same_ranges(data_min_max):
    same = data_min_max[data_min_max['Same']==True]
    minMaxRangesSame = pd.pivot_table(same,
                                 values=['PC_dia', 'SC_dia'],
                                 index='Plus_Num',
                                 aggfunc={'PC_dia': ['min', 'max'],
                                          'SC_dia': ['min', 'max']}
                                 )
    return (minMaxRangesSame)


def get_cable_data():
    data_cable = pd.read_csv("cable_criteria.csv")
    data_cable.columns = ['Desc', 'Code', 'Dia', 'Drill', 'Drill_fra','Sleeve',
       'Sleve_fra', 'Dia_MM', 'Dril_MM', 'Sleeve_MM']
    return data_cable

def get_min_max_ranges(data_min_max):
    # pivot table containing min and max values - grouped by WM (PC_dia and SC_dia min and max)
    minMaxRanges2 = pd.pivot_table(data_min_max,
                                 values=['PC_dia', 'SC_dia'],
                                 index='Plus_Num',
                                 aggfunc={'PC_dia': ['min', 'max'],
                                          'SC_dia': ['min', 'max']}
                                 )
    return(minMaxRanges2)


def  get_price_code_data():
    price_code_data = pd.read_csv("price_code.csv")
    price_code_data.set_index('wm', inplace=True)
    return price_code_data
# get min max (cable rules) data
data_min_max = get_min_max_data()
min_max_ranges = get_min_max_ranges(data_min_max)
min_max_same_ranges = get_min_max_same_ranges(data_min_max)

#get cable base data AO... file 
data_cable = get_cable_data()
#get price code matrix data
data_price_code = get_price_code_data()

# cross check the cable code based on cable description. Returns the first element found
def get_cable_code(desc,data_cable):
    temp = data_cable[data_cable['Desc']==desc]['Code'].to_list()
    if (len(temp)> 1):
        result= temp[0]
    else:
        result = temp
    return result[0]

# cross check the cable diameter based on cable code. Returns the first element found
def get_cable_dia(code,data_cable):
    temp = data_cable[data_cable['Code']==code]['Dia'].to_list()
    if (len(temp)> 1):
        result= temp[0]
    else:
        result = temp
    return result[0]
def WM_rules1(p_dia,min_max_same_ranges):
    for row in min_max_same_ranges.index.tolist():
        p_min = float(min_max_same_ranges.loc[row]['PC_dia']['min'])
        p_max = float(min_max_same_ranges.loc[row]['PC_dia']['max'])
        #print(p_min, type(p_min), p_max, type(p_max), p_dia, type(p_dia))
        if (p_min <= p_dia <= p_max):
            return (row)

def WM_rules2(p_dia,s_dia,min_max_ranges):
    for row in min_max_ranges.index.tolist():
        p_min = float(min_max_ranges.loc[row]['PC_dia']['min'])
        p_max = float(min_max_ranges.loc[row]['PC_dia']['max'])
        s_min = float(min_max_ranges.loc[row]['SC_dia']['min'])
        s_max = float(min_max_ranges.loc[row]['SC_dia']['max'])
        #print(p_min,p_dia,p_max,p_min,p_dia,p_max, row)
        if (p_min <= p_dia <= p_max) and (s_min <= s_dia <= s_max):
            return row

def getWM (p_code,s_code,p_dia,s_dia, min_max_ranges,min_max_same_ranges):
    #rule 1
    result = 0
    min_abs = float(min_max_same_ranges.loc[25]['PC_dia']['min'])
    if p_code == s_code:
        result = WM_rules1(p_dia,min_max_same_ranges)
    else:
        result = WM_rules2(p_dia,s_dia, min_max_ranges)    
    #adjusted for cables that are lower than 25 - needs to be checked by engineering. 
    #Instead of this we can add a condition on 25WM (eliminate the >= just for this case)
    if result == 0:
        result = 25
    return(result)

def get_prefix(reclaimed,low_emissions,application):
    if ((reclaimed == 'yes') and (low_emissions == 'yes')):
        return 'XLHD'
    elif (low_emissions == 'yes') and (application =='cathodic'):
        return 'XLCA'
    elif (reclaimed == 'yes'):
        return 'HD'
    elif (low_emissions == 'yes'):
        return 'XL'
    elif (application == 'cathodic'):
        return 'CA'

def get_family(family):
    return family

def get_price_code(rail_site, wm):
    # all these can be easily replaced with lookup in the price_code table. It's more elegant and less error prone
    if rail_site == 'yes' and wm>300 :
        desc = 'PB50'
    elif  44 < wm <= 300:
        desc = 'P10'
    else:
        desc = 'SB02'
    
    if wm>300:
        code = 'D'
    elif 44 < wm <= 300:
        code = 'C'
    else:
        code = 'T'
    return (code,desc)


def generate_pn(price_code, prefix,family,p_code,s_code,suffix ):
    
    if price_code in ('C','D','T'):
        if family == 'SS' and p_code==s_code:
            return prefix + family + price_code + suffix
        else:
            return prefix + family + price_code + str(s_code) + suffix



@app.route('/', methods=['GET', 'POST'])
def index():

    if request.method == 'POST':
        # Retrieve user inputs from the form
        application = request.form['application']
        connection = request.form['connection']
        family = request.form['family']
        primary_style = request.form['primary_style']
        secondary_style = request.form['secondary_style']
        primary_conductor = request.form['primary_conductor']
        secondary_conductor = request.form['secondary_conductor']
        reclaimed = request.form['reclaimed']
        low_emissions = request.form['low_emissions']
        rail_site = request.form['rail_site']
        
        #cable details
        p = primary_conductor + " " + primary_style
        s = secondary_conductor + " " + secondary_style
        print(f"p: {p}")
        print(f"s: {s}")

        #get cable dimmensions and code
        p_code = get_cable_code(p,data_cable)
        s_code = get_cable_code(s,data_cable)
        p_dia = get_cable_dia(p_code,data_cable)
        s_dia = get_cable_dia(s_code,data_cable)
        print(f"s_dia: {s_dia}")
        print(f"s_code: {s_code}")
        #get the variables for the generate part number
        prefix = get_prefix(reclaimed,low_emissions,application)
        print(f"prefix: {prefix}")
        family = get_family(family)
        wm = getWM(p_code,s_code,p_dia,s_dia, min_max_ranges,min_max_same_ranges)
        print(f"wm: {wm}")
        price_code,price_desc = get_price_code(rail_site, wm)
        print(f"price_code: {price_code}")
        #don't know how to calculate suffix
        suffix = ''
        pn = generate_pn(price_code, prefix,family,p_code,s_code,suffix)

        # Return the same input values as JSON
        return jsonify({
            'prefix': prefix,
            'family': family,
            'WM': wm,
            'price_code': price_code,
            'price_code_details': price_desc,
            'part_number': pn,
            'primary_cable': p,
            'secondary_cable': s
        })

    # Render the form template if it's a GET request
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
