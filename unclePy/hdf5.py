import h5py
import numpy as np
import pandas as pd
import re
from datetime import datetime
import sqlalchemy
import yaml


class HDF5:
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
    uncle_experiment_id : int
        Database ID for UNcle experiment
    well_set_id : int
        Database ID for associated well set

    Methods
    -------
    exp_file_name()
        Returns name of file associated with experiment

    exp_name()
        Returns name of experimental run

    exp_date()
        Returns date of experiment

    exp_inst_num()
        Returns number of instrument used in experiment

    exp_product()
        Returns product tested in experiment

    exp_plate_type(return_id)
        Returns name or ID of plate/screen used in experiment

    exp_generation()
        Returns generation of plate layout used in experiment

    exp_plate_side()
        Returns side of plate used in experiment (L/R)

    wells(include_uni_address)
        Returns names of wells used in experiment

    samples()
        Returns sample names/descriptions

    well_exists(well)
        Returns True/False if well ID exists for well

    get_exp()
        Returns experiment ID, if it exists

    exp_exists()
        Returns T/F if experiment exists

    exp_confirm_created()
        Checks experiment has been saved to database. Returns nothing.

    get_exp_instrument()
        Returns instrument ID, if it exists

    exp_instrument_assigned()
        Returns instrument ID, if it has been assigned to experiment

    exp_instrument_exists()
        Returns T/F if experiment exists

    get_exp_product()
        Returns product ID, if it exists

    exp_product_assigned()
        Returns product ID, if it has been assigned to experiment

    exp_product_exists()
        Returns T/F if product exists

    write_exp_set_info_sql(self, datetime_needed = True)
        Writes experiment set metadata to PostgreSQL database

    write_exp_info_sql(datetime_needed)
        Writes experiment metadata to PostgreSQL database

    write_instrument_info_sql(datetime_needed)
        Writes instrument metadata to PostgreSQL database

    write_product_info_sql()
        Writes product info metadata to PostgreSQL database

    write_summary_sql(df)
        Writes combined SLS and DLS summary data to PostgreSQL database

    df_to_sql(df, well)
        Returns input dataframe with additional columns added to match
        associated database tables

    write_processing_status(status, error)
        Writes .uni processing status to PostgreSQL database

    well_name_to_num(well)
        Returns well number converted from input well name
        Example: 'A1' -> 'Well_01'

    well_name_to_id(well)
        Returns database well ID for input well name

    well_name_to_summary(well)
        Returns database summary ID for input well name
    """
    def __init__(self, file_path, uncle_experiment_id, well_set_id,):
        self.file = h5py.File(file_path, 'r')
        self.uncle_experiment_id = uncle_experiment_id
        self.well_set_id = well_set_id

        with open("/var/www/ebase/current/config/database.yml", 'r') \
                as stream:
            info = yaml.safe_load(stream)
            username = info['production']['username']
            password = info['production']['password']
            host = info['production']['host']
            database = info['production']['database']

        self.engine = sqlalchemy.create_engine('postgresql://{}:{}@{}:5432/{}'.
                                               format(username,
                                                      password,
                                                      host,
                                                      database))

        # self.engine = sqlalchemy.create_engine('postgresql://{}:{}@{}:5432/{}'.
        #                                        format('postgres',
        #                                               '',
        #                                               'localhost',
        #                                               'ebase_dev'))
        with self.engine.connect() as con:
            query = sqlalchemy.text("SELECT uncle_experiment_set_id "
                                    "FROM uncle_experiments "
                                    "WHERE id = {};".
                                    format(self.uncle_experiment_id))
            exp_set_id = con.execute(query)
            exp_set_id = exp_set_id.mappings().all()
        self.exp_set_id = exp_set_id[0]['uncle_experiment_set_id']

    # ----------------------------------------------------------------------- #
    # EXPERIMENT METADATA                                                     #
    # ----------------------------------------------------------------------- #
    def exp_file_name(self):
        """
        Returns
        -------
        str
            Name of current run
        """
        file_name = self.file.filename.split('/')[-1]
        assert file_name[-4:].lower() == '.uni', \
            'File extension does not match [.uni]. Ensure correct file has ' \
            'been uploaded and extension matches [.uni].'

        run_name = file_name[:-4]
        assert run_name.count('-') == 3, \
            'Incorrect file name format. Format should be: ' \
            'Date (YYMMDD) - Instrument # - Protein Name - ' \
            'Plate Type/Generation/Side'
        return run_name

    def exp_name(self):
        """
        Returns
        -------
        str
            Name of experiment - same as file name without plate side
        """
        return self.exp_file_name()[:-1]

    def exp_date(self):
        """
        Returns
        -------
        pd.Timestamp
            Date of experiment
        """
        date = self.exp_file_name().split('-')[0]
        assert date.isnumeric(),\
            'Incorrect date format. Format should be: YYMMDD'
        assert len(date) == 6,\
            'Incorrect date format. Format should be: YYMMDD'
        return pd.to_datetime(date, yearfirst = True)

    def exp_inst_num(self):
        """
        Returns
        -------
        int
            Instrument number used in experiment
        """
        inst_num = self.exp_file_name().split('-')[1]
        assert inst_num.isnumeric(),\
            'Incorrect instrument number format. Format should be: ##'
        return int(inst_num)

    def exp_product(self):
        """
        Returns
        -------
        str
            Product used in experiment
        """
        return self.exp_file_name().split('-')[2]

    def exp_plate_type(self, return_id = False):
        """
        Parameters
        ----------
        return_id : bool (default = False)
            Whether to return database IDs or names

        Returns
        -------
        str (if return_id = False)
            Name of plate type used in experiment
        int (if return_id = True)
            ID of plate type used in experiment
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text(
                "SELECT upt.name, upt.id "
                "FROM uncle_plate_types upt "
                "JOIN well_sets ws "
                "   ON ws.uncle_plate_type_id = upt.id "
                "JOIN uncle_experiment_sets ues "
                "   ON ues.well_set_id = ws.id "
                "WHERE ues.well_set_id = {}".format(
                    self.well_set_id
                ))
            result = con.execute(query)
            result = result.mappings().all()

        if return_id:
            return result[0]['id']
        else:
            return result[0]['name']

    def exp_generation(self):
        """
        Returns
        -------
        str
            Generation of plate layout used in experiment
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text(
                "SELECT ws.uncle_plate_generation "
                "FROM well_sets ws "
                "WHERE ws.id = {}".format(
                    self.well_set_id
                ))
            result = con.execute(query)
            result = result.mappings().all()

        return result[0]['uncle_plate_generation']

    def exp_plate_side(self):
        """
        Returns
        -------
        str
            Plate side used in experiment
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text(
                "SELECT plate_side "
                "FROM uncle_experiments ue "
                "WHERE ue.id = {}".format(
                    self.uncle_experiment_id
                ))
            plate_side = con.execute(query)
            plate_side = plate_side.mappings().all()[0]['plate_side']

        assert plate_side.lower() in ['l', 'r'],\
            'Incorrect plate side. Plate side should be one of: L, R'
        return plate_side

    # ----------------------------------------------------------------------- #
    # EXPERIMENT INFORMATION                                                  #
    # ----------------------------------------------------------------------- #
    def wells(self, include_uni_address = False):
        """
        Returns
        -------
        dict, if include_uni_address == True
            {uni capillary address: layout address}
        np.array, if include_uni_address == False
            Layout addresses

        Examples
        --------
        include_uni_address == True
            {'A1': 'A1', 'B1': 'A2', 'C1': 'A3', 'D1': 'A4', ...}
        include_uni_address == False
            np.array(['A1', 'B1', ...])
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text(
                "SELECT w.layout_address, w.uni_capillary_address "
                "FROM wells w "
                "JOIN well_set_wells wsw "
                "   ON wsw.well_id = w.id "
                "JOIN uncle_experiment_sets ues "
                "   ON ues.well_set_id = wsw.well_set_id "
                "WHERE ues.well_set_id = {} "
                "AND w.uni_plate_side = '{}' "
                "ORDER BY w.id".format(
                    self.well_set_id,
                    self.exp_plate_side()
                ))
            result = con.execute(query)
            result = result.mappings().all()

            sorted_result =\
                sorted(result,
                       key = lambda x: (x['uni_capillary_address'][1:],
                                        x['uni_capillary_address'][0]))

        if include_uni_address:
            wells = {}
            for well in sorted_result:
                wells[well['uni_capillary_address']] = well['layout_address']
        else:
            wells = []
            for well in sorted_result:
                wells = np.append(wells, well['layout_address'])
        return wells

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
        mapping = self.wells(include_uni_address = True)
        samples = []

        for i in self.file['Application1']['Run1']['SampleData']:
            sample_name = i[1].decode('utf-8').split(' ')
            well = sample_name[-1]
            if not mapping.get(well, False):
                # If well does not actually exist in template
                continue

            mapped_well = mapping[well]
            if self.well_exists(mapped_well):
                corrected_sample_name = [mapped_well if i == well
                                         else i for i in sample_name]
                samples = np.append(samples, ' '.join(corrected_sample_name))
        return samples

    def well_exists(self, well):
        """
        Parameters
        ----------
        well : str
            Single well name, e.g. 'A1'

        Returns
        -------
        bool
            True: if well ID exists for well
            False: if well ID does not exist for well
        """
        try:
            self.well_name_to_id(well)
            return True
        except IndexError:
            return False

    # ----------------------------------------------------------------------- #
    # EXPERIMENT CHECKS                                                       #
    # ----------------------------------------------------------------------- #
    def get_exp(self):
        """
        Returns
        -------
        int
            Experiment ID, if it exists
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text("SELECT id "
                                    "FROM uncle_experiments "
                                    "WHERE uncle_experiment_set_id = '{}' "
                                    "AND uncle_instrument_id = '{}' "
                                    "AND plate_side = '{}' "
                                    "AND date = '{}';".format(
                                        self.exp_set_id,
                                        self.get_exp_instrument(),
                                        self.exp_plate_side(),
                                        self.exp_date()))
            exp_id = con.execute(query)
            exp_id = exp_id.mappings().all()
        if exp_id:
            return exp_id[0]['id']
        else:
            return

    def exp_exists(self):
        """
        Returns
        -------
        bool
            True: if experiment exists
            False: if experiment does not exist
        """
        if self.get_exp():
            return True
        else:
            return False

    def exp_confirm_created(self):
        """
        Returns
        -------
        None
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text("SELECT id "
                                    "FROM uncle_experiments "
                                    "WHERE id = '{}';".
                                    format(self.uncle_experiment_id))
            exp = con.execute(query)
            exp = exp.mappings().all()
        assert exp, 'Could not find UNcle experiment. ' \
                    'Confirm experiment has been created.'

    def get_exp_instrument(self):
        """
        Returns
        -------
        int
            Instrument ID: if experiment instrument exists
            0: if experiment instrument does not exist
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text("SELECT id "
                                    "FROM uncle_instruments "
                                    "WHERE id = '{}';".
                                    format(self.exp_inst_num()))
            inst_id = con.execute(query)
            inst_id = inst_id.mappings().all()

        if inst_id:
            return inst_id[0]['id']
        else:
            return 0

    def exp_instrument_assigned(self):
        """
        Returns
        -------
        bool
            True: if instrument has been assigned to UncleExperimentSet
            False: if instrument has not been assigned to UncleExperimentSet
        """
        with self.engine.connect() as con:
            inst_id = con.execute("SELECT uncle_instrument_id "
                                  "FROM uncle_experiments "
                                  "WHERE id = '{}';".
                                  format(self.uncle_experiment_id))
            inst_id = inst_id.mappings().all()

        if inst_id:
            return inst_id[0]['uncle_instrument_id']
        else:
            return False

    def exp_instrument_exists(self):
        """
        Returns
        -------
        bool
            True: if instrument exists
            False: if instrument does not exist
        """
        if self.get_exp_instrument():
            return True
        else:
            return False

    def get_exp_product(self):
        """
        Returns
        -------
        int
            Product ID, if it exists
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text("SELECT id "
                                    "FROM products "
                                    "WHERE name = '{}';".
                                    format(self.exp_product()))
            prod_id = con.execute(query)
            prod_id = prod_id.mappings().all()

        if prod_id:
            return prod_id[0]['id']
        else:
            return False

    def exp_product_assigned(self):
        """
        Returns
        -------
        bool
            True: if product has been assigned to UncleExperimentSet
            False: if product has not been assigned to UncleExperimentSet
        """
        with self.engine.connect() as con:
            prod_id = con.execute("SELECT product_id "
                                  "FROM uncle_experiment_sets "
                                  "WHERE id = '{}';".
                                  format(self.exp_set_id))
            prod_id = prod_id.mappings().all()

        if prod_id:
            return prod_id[0]['product_id']
        else:
            return False

    def exp_product_exists(self):
        """
        Returns
        -------
        bool
            True: if product exists
            False: if product does not exist
        """
        if self.get_exp_product():
            return True
        else:
            return False

    # ----------------------------------------------------------------------- #
    # WRITE DATA TO POSTGRESQL                                                #
    # ----------------------------------------------------------------------- #
    def write_exp_set_info_sql(self, datetime_needed = True):
        """
        Parameters
        ----------
        datetime_needed : bool (default = True)
            Whether to insert "created_at", "updated_at" columns
            These are necessary for Rails tables

        Returns
        -------
        None
        """
        product_id = self.exp_product_assigned()
        if product_id:
            pass
        elif self.exp_product_exists():
            product_id = self.get_exp_product()
        # Write product info if it does not exist
        else:
            self.write_product_info_sql()
            product_id = self.get_exp_product()

        exp_set_info = {
            'name': [self.exp_name()],
            'product_id': product_id,
        }
        df = pd.DataFrame(exp_set_info)
        if datetime_needed:
            df = add_datetime(df)
        update_params = df.to_dict('records')[0]

        with self.engine.connect() as con:
            query = sqlalchemy.text(
                "UPDATE uncle_experiment_sets SET "
                "name = '{}', "
                "product_id = '{}', "
                "created_at = '{}', "
                "updated_at = '{}' "
                "WHERE id = {};".format(
                    update_params['name'],
                    update_params['product_id'],
                    update_params['created_at'],
                    update_params['updated_at'],
                    self.exp_set_id)
            )
            con.execute(query)

    def write_exp_info_sql(self, datetime_needed = True):
        """
        Parameters
        ----------
        datetime_needed : bool (default = True)
            Whether to insert "created_at", "updated_at" columns
            These are necessary for Rails tables

        Returns
        -------
        None
        """
        if self.exp_exists():
            return

        inst_id = self.exp_instrument_assigned()
        if inst_id:
            pass
        elif self.exp_instrument_exists():
            inst_id = self.get_exp_instrument()
        # Write instrument info if it does not exist
        else:
            self.write_instrument_info_sql()
            inst_id = self.get_exp_instrument()

        exp_info = {'uncle_experiment_set_id': self.exp_set_id,
                    'uncle_instrument_id': inst_id,
                    'plate_side': [self.exp_plate_side()],
                    'date': [self.exp_date()]}
        df = pd.DataFrame(exp_info)
        if datetime_needed:
            df = add_datetime(df)
        update_params = df.to_dict('records')[0]

        with self.engine.connect() as con:
            query = sqlalchemy.text(
                "UPDATE uncle_experiments SET "
                "uncle_experiment_set_id = {},"
                "uncle_instrument_id = '{}',"
                "plate_side = '{}',"
                "date = '{}',"
                "created_at = '{}',"
                "updated_at = '{}'"
                "WHERE id = {};".format(
                    update_params['uncle_experiment_set_id'],
                    update_params['uncle_instrument_id'],
                    update_params['plate_side'],
                    update_params['date'],
                    update_params['created_at'],
                    update_params['updated_at'],
                    self.uncle_experiment_id)
            )
            con.execute(query)

    def write_instrument_info_sql(self, datetime_needed = True):
        """
        Parameters
        ----------
        datetime_needed : bool (default = True)
            Whether to insert "created_at", "updated_at" columns
            These are necessary for Rails tables

        Returns
        -------
        None
        """
        if self.exp_instrument_exists() or self.exp_instrument_assigned():
            return

        inst_info = {'id': [int(self.exp_inst_num())],
                     'name': ['UNcle_{}'.format(
                         str(self.exp_inst_num()).zfill(2))],
                     'location': ['Shnider/Hough lab'],
                     'model': ['UNcle']}
        df = pd.DataFrame(inst_info)
        if datetime_needed:
            df = add_datetime(df)
        df.to_sql('uncle_instruments', self.engine, if_exists = 'append',
                  index = False)

    def write_product_info_sql(self):
        """
        Returns
        -------
        None
        """
        if self.exp_product_exists() or self.exp_product_assigned():
            return

        prod_info = {'name': [self.exp_product()],
                     'active': 'true'}
        df = pd.DataFrame(prod_info)
        df.to_sql('products', self.engine, if_exists = 'append', index = False)

    def write_summary_sql(self, df):
        """
        Parameters
        ----------
        df : pd.DataFrame
            Combined SLS and DLS summary tables

        Returns
        -------
        None
        """
        df.to_sql('uncle_summaries',
                  self.engine,
                  if_exists = 'append',
                  index = False)

    def df_to_sql(self, df, well = None):
        """
        Parameters
        ----------
        df : pd.DataFrame
            Dataframe to be modified for PostgreSQL data table
        well : str
            Single well name, e.g. 'A1'

        Returns
        -------
        pd.DataFrame
            Modified to fit database structure
        """
        df = add_datetime(df)
        if well:
            df['well'] = well

        if df.name == 'summary':
            if self.exp_exists():
                df['uncle_experiment_id'] = self.get_exp()
            # Write experimental info if it does not exist
            else:
                self.write_exp_info_sql()
                df['uncle_experiment_id'] = self.get_exp()

        return df

    def write_processing_status(self, status, error = None):
        """
        Parameters
        ----------
        status : str
            Status of .uni processing
            Current statuses: "failed", "processing", "complete", "processing"
        error : sqlalchemy.exc.SQLAlchemyError, Exception
            Traceback from any errors which happen during parsing/writing

        Returns
        -------
        None
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text("UPDATE uncle_experiment_sets "
                                    "SET processing_status = '{}' "
                                    "WHERE id = {};".format(
                                        status,
                                        self.exp_set_id))
            con.execute(query)

            if error:
                query = sqlalchemy.text("UPDATE uncle_experiments "
                                        "SET processing_errors = $${}$$ "
                                        "WHERE id = {};".format(
                                            str(error),
                                            self.uncle_experiment_id))
                con.execute(query)
            else:
                query = sqlalchemy.text("UPDATE uncle_experiments "
                                        "SET processing_errors = null "
                                        "WHERE id = {};".format(
                                            self.uncle_experiment_id))
                con.execute(query)

    # ----------------------------------------------------------------------- #
    # UTILITY FUNCTIONS                                                       #
    # ----------------------------------------------------------------------- #
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
        well_num = 'Well_{}'.format(str(well_num).zfill(2))
        return well_num

    def well_name_to_id(self, well):
        """
        Parameters
        ----------
        well : str
            Single well name, e.g. 'A1'

        Returns
        -------
        int
            Database well_id
        """
        with self.engine.connect() as con:
            query = sqlalchemy.text("SELECT well_id FROM well_set_wells "
                                    "WHERE well_set_id = {} "
                                    "AND plate_address = '{}';".
                                    format(self.well_set_id, well))
            well_id = con.execute(query)
            well_id = well_id.mappings().all()
        return well_id[0]['well_id']

    def well_name_to_summary(self, well):
        """
        Parameters
        ----------
        well : str
            Single well name, e.g. 'A1'

        Returns
        -------
        int
            Database summary_id
        """
        if well[0].isalpha():
            well = self.well_name_to_id(well)
        with self.engine.connect() as con:
            query = sqlalchemy.text("SELECT id "
                                    "FROM uncle_summaries "
                                    "WHERE well_id = {};".format(well))
            summary_id = con.execute(query)
            summary_id = summary_id.mappings().all()
        return summary_id[0]['id']


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
