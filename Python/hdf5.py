import h5py
import numpy as np
import pandas as pd
import re
from datetime import datetime
from sqlalchemy import create_engine


class HDF5:
    # TODO insert more assertions for code checking
    # TODO update variable names to be more descriptive
    # TODO either add more "examples" or remove some - make more consistent

    """
    Generic class to load .uni (HDF5) files

    Assumed naming convention:
        Date-InstNum-Prod-PlateInfo.uni
            Date: YYMMDD (e.g. 210602)
            InstNum: Instrument number (e.g. 01)
            Prod: Product name (e.g. Seq1 Cas9)
            PlateInfo: Plate type, generation, side (e.g. pH003R)
            Example: 210602-01-Seq1 Cas9-pH003R.uni

    Attributes
    ----------
    file_path : str
        .uni (HDF5) file to load

    Methods
    -------
    run_name()
        Returns name of experimental run

    exp_date()
        Returns date of experiment

    exp_inst_num()
        Returns number of instrument used in experiment

    exp_product()
        Returns product tested in experiment

    exp_plate_type()
        Returns type of plate/screen used in experiment (pH, cond, gen)

    exp_generation()
        Returns generation of plate layout used in experiment

    exp_plate_side()
        Returns side of plate used in experiment (L/R)

    write_experiment_info_sql(username, password, host, database,
                              datetime_needed)
        Saves experiment metadata to PostgreSQL database

    write_instrument_info_sql(username, password, host, database,
                              datetime_needed)
        Saves instrument metadata to PostgreSQL database

    wells()
        Returns names of wells used in experiment

    well_name_to_num(well)
        Returns well number converted from input well name
        Example: 'A1' -> 'Well_01'

    samples()
        Returns sample names/descriptions

    """
    def __init__(self, file_path):
        self.file = h5py.File(file_path, 'r')

    def exp_name(self):
        """
        Returns
        -------
        str
            Name of current run
        """
        run_name = self.file['Application1']['Run1'].attrs['Run Name'].\
            decode('utf-8')
        return run_name

    def exp_date(self):
        """
        Returns
        -------
        pd.Timestamp
            Date of experiment
        """
        date = self.exp_name().split('-')[0]
        return pd.to_datetime(date, yearfirst = True)

    def exp_inst_num(self):
        """
        Returns
        -------
        int
            Instrument number used in experiment
        """
        return int(self.exp_name().split('-')[1])

    def exp_product(self):
        """
        Returns
        -------
        str
            Product used in experiment
        """
        return self.exp_name().split('-')[2]

    def exp_plate_type(self):
        """
        Returns
        -------
        str
            Plate type used in experiment
        """
        plate_info = self.exp_name().split('-')[-1]
        plate_type = re.search(r'\D+', plate_info)
        return plate_type.group()

    def exp_generation(self):
        """
        Returns
        -------
        str
            Generation of plate layout used in experiment
        """
        plate_info = self.exp_name().split('-')[-1]
        plate_gen = re.search(r'\d+', plate_info)
        return plate_gen.group()

    def exp_plate_side(self):
        """
        Returns
        -------
        str
            Plate side used in experiment
        """
        plate_info = self.exp_name().split('-')[-1]
        plate_side = re.search(r'\D+$', plate_info)
        return plate_side.group()

    def write_experiment_info_sql(self, username, password, host, database,
                                  datetime_needed = True):
        """
        Parameters
        ----------
        username : str
            Username for database access (e.g. "postgres")
        password : str
            Password for database access (likely none, i.e. empty string: "")
        host : str
            Host address for database access (e.g. "ebase-db-c")
        database : str
            Database name (e.g. "ebase_dev")
        datetime_needed : bool (default = True)
            Whether to insert "created_at", "updated_at" columns
            These are necessary for Rails tables

        Returns
        -------
        None
        """
        # TODO complete this with real info
        engine = create_engine('postgresql://{}:{}@{}:5432/{}'.format(
            username, password, host, database))

        with engine.connect() as con:
            inst_id = con.execute("SELECT id FROM uncle_instruments "
                                  "WHERE id = {};".
                                  format(self.exp_inst_num()))
            prod_id = con.execute("SELECT id FROM products "
                                  "WHERE name = '{}';".
                                  format(self.exp_product()))

        # TODO what to do if instrument/product do not exist?

        try:
            inst_id = inst_id.mappings().all()[0]['id']
        except (TypeError, AttributeError, IndexError):
            inst_id = None

        try:
            prod_id = prod_id.mappings().all()[0]['id']
        except (TypeError, AttributeError, IndexError):
            prod_id = None

        exp_info = {'name': [self.exp_name()],
                    'date': [self.exp_date()],
                    'uncle_instrument_id': inst_id,
                    'product_id': prod_id,
                    'exp_type': [self.exp_plate_type()],
                    'plate_generation': [self.exp_generation()],
                    'plate_side': [self.exp_plate_side()]}
        df = pd.DataFrame(exp_info)
        if datetime_needed:
            df = add_datetime(df)
        df.to_sql('uncle_experiments', engine, if_exists = 'append',
                  index = False)

    def write_instrument_info_sql(self, username, password, host, database,
                                  datetime_needed = True):
        """
        Parameters
        ----------
        username : str
            Username for database access (e.g. "postgres")
        password : str
            Password for database access (likely none, i.e. empty string: "")
        host : str
            Host address for database access (e.g. "ebase-db-c")
        database : str
            Database name (e.g. "ebase_dev")
        datetime_needed : bool (default = True)
            Whether to insert "created_at", "updated_at" columns
            These are necessary for Rails tables

        Returns
        -------
        None
        """
        # TODO complete this with real info
        inst_info = {'id': [int(self.exp_inst_num())],
                     'name': ['Uncle_01'],
                     'location': ['Shnider/Hough lab'],
                     'model': ['Uncle']}
        df = pd.DataFrame(inst_info)
        if datetime_needed:
            df = add_datetime(df)

        engine = create_engine('postgresql://{}:{}@{}:5432/{}'.format(
            username, password, host, database))
        df.to_sql('uncle_instruments', engine, if_exists = 'append',
                  index = False)

    def wells(self):
        """
        Returns
        -------
        np.array
            Well names

        Examples
        --------
        np.array(['A1', 'B1', ...])
        """
        wells = []
        for i in self.file['Application1']['Run1']['SampleData']:
            wells = np.append(wells, i[0].decode('utf-8'))
        return wells

    def well_name_to_num(self, well):
        """
        Parameters
        ----------
        well : str
            Single well name, e.g. 'A1'

        Returns
        -------
        string
            Well number, e.g. 'Well_01'
        """
        well_num = np.argwhere(self.wells() == well)[0][0] + 1
        well_num = f'Well_{well_num:02}'
        return well_num

    def samples(self):
        """
        Returns
        -------
        np.array
            Sample names

        Examples
        --------
        np.array(['0.1 mg/ml Uni A1', '0.1 mg/ml Uni B1', ...])
        """
        samples = []
        for i in self.file['Application1']['Run1']['SampleData']:
            samples = np.append(samples, i[1].decode('utf-8'))
        return samples


def df_to_sql(df, well = None):
    """
    Parameters
    ----------
    df : pd.DataFrame
        Dataframe to be modified for PostgreSQL data table
    well : str

    well
    df

    Returns
    -------
    pd.DataFrame
        Modified to fit database structure
    """
    df['export_type'] = df.name.split('_')[0]
    df = add_datetime(df)
    if well:
        df['well'] = well
    if len(df.name.split('_')) == 2:
        df['dls_data_type'] = df.name.split('_')[1]
    return df


def add_datetime(df):
    """
    Parameters
    ----------
    df : pd.DataFrame
        Dataframe to add created_at, updated_at columns to

    Returns
    -------
    pd.DataFrame
        Input dataframe with created_at, updated_at columns added
    """
    dt = datetime.now()
    df['created_at'] = dt
    df['updated_at'] = dt
    return df


def verify(value):
    """
    Parameters
    ----------
    value : int, float
        Any value to verify is legitimate

    Returns
    -------
    int, float, np.nan
        Depends on input value
        Returns input value if valid, otherwise np.nan
    """
    if value != -1:
        return value
    else:
        return np.nan


h1 = HDF5('/Users/jmiller/Desktop/UNcle Files/uni files/210602-01-Seq1 Cas9-pH003R.uni')
h2 = HDF5('/Users/jmiller/Desktop/UNcle Files/uni files/Gen6 uni 1,2,3.uni')
save_path = '/Users/jmiller/Desktop/UNcle Files/Misc/uncle_out.xlsx'

"""
Gen6 1,2,3 = 210607-01-T4 RNA Ligase-Gen006L
Gen6 4,5,6 = 210607-01-T4 RNA Ligase – Gen006R
pH 1,2,3 = 210608-01-T4 RNA Ligase-pH003L
pH 4,5 = 210608-01-T4 RNA Ligase-pH003R
"""
