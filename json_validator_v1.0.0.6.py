#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This script validates that each line of a given file contains valid
JSON in the format expected by metadata ingestion.
"""
__author__ = "Joe Delfino (joe@echonest.com)"
__date__   = "Fri Sep 16 11:06:32 2011"
__version__ = "1.0.0.6"

import sys
import codecs
from optparse import OptionParser
try:
    import simplejson as json
except ImportError:
    import json

JSON_UNICODE_PROBLEMS = [u'\u2028', u'\u2029']

def safe_file_reader(f): 
    nextLine = ''
    while True:
        try:
            nextLine = nextLine + f.next()
        except StopIteration:
            if nextLine:
                yield nextLine
            return
        if nextLine[-1] in JSON_UNICODE_PROBLEMS:
            continue
        else:
            yield nextLine
            nextLine = ''

def _indent(val, indent):
    return '\n' + (' ' * indent * 4) + val

def valid_entry(field):
    if type(field) == unicode:
        return not field.strip() in [None, '']
    return True


class Field(dict):

    def __init__(self, name, expectedValue, disallowedFields=[]):
        self.name = name
        self.expectedValue = expectedValue
        self.disallowedFields = disallowedFields


class FieldChecker(object):
    """
    An abstract base class for objects that can validate that a given object
    has a correct structure/type.  Subclasses must implement _validate(),
    stringify(), and topLevelType()
    """
    
    def __str__(self):
        return self.stringify()

    def stringify(self, indent=0):
        raise NotImplementedError()

    def topLevelType(self):
        raise NotImplementedError()

    def _validate(self, candidate, required=False):
        raise NotImplementedError()
        
    def validate(self, candidate, required=False):
        """
        Return a list of errors found in candidate, or an empty list if
        none are found
        """
        
        if not isinstance(candidate, self.topLevelType()):
            return ['Expected type: "' + 
                    self.topLevelType().__name__ + '", ' + 
                    'but found type: "' + type(candidate).__name__ + '"'], []
        return self._validate(candidate, required)


class DictTypeChecker(FieldChecker):
    """
    Check a dict to ensure that each key and value are of an expected type.  Does not currently support
    nesting of FieldCheckers
    """

    def __init__(self, expectedKeyTypeInstance, expectedValueTypeInstance, all_required=False):
        super(DictTypeChecker, self).__init__()
        self.expectedKeyTypeInstance = expectedKeyTypeInstance
        self.expectedValueTypeInstance = expectedValueTypeInstance
        self.all_required = all_required

    def stringify(self, indent = 0):
        keyTypeName = type(self.expectedKeyTypeInstance).__name__ \
            if not isinstance(self.expectedKeyTypeInstance, FieldChecker) \
            else self.expectedKeyTypeInstance.topLevelType().__name__

        valueTypeName = type(self.expectedValueTypeInstance).__name__ \
            if not isinstance(self.expectedValueTypeInstance, FieldChecker) \
            else self.expectedValueTypeInstance.topLevelType().__name__
            
        return _indent('dict of "' + keyTypeName + '":"' + valueTypeName + '"', indent)
        
    def topLevelType(self):
        return dict

    def _check_field(self, fieldName, candidateField, expectedValue, errors, warngings, required):
        if isinstance(expectedValue, FieldChecker):
            errorString = 'Found error in ' + fieldName + ' "' + unicode(candidateField) + '": '
            errors.extend(errorString + x for x in 
                          expectedValue.validate(candidateField))
                              
        elif not isinstance(candidateField, type(expectedValue)):
            #csv reader reads this as strings, try to convert to an int
            if expectedValue == int():
                try:
                    int(candidateField)
                except (TypeError, ValueError) as e:
                    errors.append(
                        fieldName + ' "' + unicode(candidateField) + '" had incorrect type. ' + 
                        'Expected: "int" but found: "' +  type(candidateField).__name__ + '"')
            else:
                errors.append(
                    fieldName + ' "' + unicode(candidateField) + '" had incorrect type. ' + 
                    'Expected: "' + 
                    type(expectedValue).__name__ + '" ' + 
                    'but found: "' + 
                    type(candidateField).__name__ + '"')
                        
        if required and not valid_entry(candidateField):
           warngings.append('"'+ fieldName +'" was required, but found an invalid entry of "' + unicode(candidateField)+ '"')
                    
    def _validate(self, candidateDict, required=False):
        assert isinstance(candidateDict, self.topLevelType())
        errors = []
        warnings = []

        for key, value in candidateDict.iteritems():
            self._check_field("key", key, self.expectedKeyTypeInstance, errors, warnings, required)
            self._check_field("value", value, self.expectedValueTypeInstance, errors, warnings, required)

        return errors, warnings

class StringListChecker(FieldChecker):
    """
    Check a string to make sure it is one of a set of fields
    """

    def __init__(self, fields):
        super(StringListChecker, self).__init__()
        self.fields = fields

    def stringify(self, indent = 0):
        return _indent('string in %r' % self.fields, indent)
        

    def topLevelType(self):
        return unicode
    
    def _validate(self, candidate, required=False):
        assert isinstance(candidate, self.topLevelType())
        errors = []
        warnings = []
        
        if not candidate in self.fields:
            errors.append(
                'Element "' + candidate + '" was not in list %r ' % self.fields)

        return errors, warnings


class ListTypeChecker(FieldChecker):
    """
    Check a list to ensure that each element is of an expected type.
    Does not currently support nesting of FieldCheckers
    """

    def __init__(self, expectedTypeInstance, all_required=False):
        super(ListTypeChecker, self).__init__()
        self.expectedTypeInstance = expectedTypeInstance
        self.all_required = all_required

    def stringify(self, indent = 0):
        typeName = type(self.expectedTypeInstance).__name__ \
            if not isinstance(self.expectedTypeInstance, FieldChecker) \
            else self.expectedTypeInstance.topLevelType().__name__
            
        return _indent('list of "' + typeName + '"', indent)
        

    def topLevelType(self):
        return list
    
    def _validate(self, candidateList, required=False):
        assert isinstance(candidateList, self.topLevelType())
        errors = []
        warnings = []

        
        for pos, elem in enumerate(candidateList):
            if isinstance(self.expectedTypeInstance, FieldChecker):
                errorString = 'Found error in element at index ' + str(pos) + ': '
                errs, warns = self.expectedTypeInstance.validate(elem, required)
                errors.extend(errorString + x for x in errs)
                warnings.extend(x for x in warns)

            elif not isinstance(elem, type(self.expectedTypeInstance)):
                errors.append(
                    'Element at index ' + str(pos) + ' had incorrect type. ' +
                    'Expected: "' +
                     type(self.expectedTypeInstance).__name__ + '" ' + 
                    'but found: "' + 
                    type(elem).__name__ + '"')

        return errors, warnings

class DictFieldChecker(FieldChecker):
    """
    This class is initialized with a set of required and optional fields, along with
    expected types for each field.  Given a candidate dictionary, the validate() function
    will compare the candidate to the expected structure, and return a list of errors (if any)
    found in the candidate.
    See the variable 'fields' further down in this file for an example of constructing.
    """
    
    def __init__(self, required, optional, historical, all_required=False):
        super(DictFieldChecker, self).__init__()
        self.required = required
        self.optional = optional
        self.historical = historical
        self.all_required = False

        self.optional_dict = dict([(x.name, x) for x in historical + optional])

    def topLevelType(self):
        return dict

    ######### Stringification ##########
    
    def _stringify_fields(self, items, required, indent):
        retVal = ''
        for field in sorted(items, key=lambda x: x.name):
            fieldName, expectedValue = field.name, field.expectedValue

            typeName = type(expectedValue).__name__ \
                if not isinstance(expectedValue, FieldChecker) \
                else expectedValue.topLevelType().__name__
            
            req = 'required' if required else 'optional'
            retVal += _indent('"' + fieldName + '": type "' + typeName +
                              '", ' + req, indent)
            if isinstance(expectedValue, FieldChecker):
                nestedString = expectedValue.stringify(indent+1)
                if nestedString:
                    retVal += ':' + nestedString
        return retVal
                
    def stringify(self, indent=1):
        retVal = _indent('{', indent-1)
        retVal += self._stringify_fields(self.required,
                                         True,
                                         indent)
        retVal += self._stringify_fields(self.optional,
                                         False,
                                         indent)
        return retVal + _indent('} ', indent-1)
                       
    ######### Field Checking ##########
    
    def _type_error(self, fieldName, expectedItem, actualItem):
        return 'Field "' + fieldName + '" had incorrect type. ' \
            'Expected: "' + type(expectedItem).__name__ + '" ' \
            'but found: "' + type(actualItem).__name__ + '"'
        
    def _check_field(self, fieldName, candidateField, validationField, candidateFields, errors, warnings, required):
        expectedValue = validationField.expectedValue
        if isinstance(expectedValue, FieldChecker):
            errorString = 'Found error in field "' + fieldName + '": '
            errs, warns = expectedValue.validate(candidateField, required)
            errors.extend(
                errorString + x for x in errs)
            warnings.extend(x for x in warns)
            
        elif not isinstance(candidateField, type(expectedValue)):
             #csv reader reads this as strings, try to convert to an int
            if type(expectedValue) == int:
                try:
                    int(candidateField)   
                except (TypeError, ValueError) as e:                 
                    errors.append(self._type_error(fieldName, int(), candidateField))
            else:
                errors.append(self._type_error(fieldName,
                                               expectedValue,
                                               candidateField))
        if required and not valid_entry(candidateField):
            warnings.append('"'+ fieldName +'" was required, but found an invalid entry of "' + unicode(candidateField)+ '"')
        
        for unallowed in validationField.disallowedFields:
            if unallowed in candidateFields:
                errors.append("Fields '%s' and '%s' are not allowed to be attached to the same entity." % 
                    (validationField.name, unallowed))

    def _validate(self, originalCandidate, required=False):
        assert isinstance(originalCandidate, self.topLevelType())
        errors = []
        warnings = []

        candidate = originalCandidate.copy()
        candidate_fields = originalCandidate.keys()

        # first, process all required fields
        for field in self.required:
            fieldName = field.name
            if not fieldName in candidate:
                errors.append('Did not find required field "' + fieldName + '"')
                continue

            candidateField = candidate.pop(fieldName) 
            self._check_field(fieldName, candidateField, field, candidate_fields, errors, warnings, True)

        # at this point, all required fields have been removed
        # iterate through remaining fields, ensuring that everything
        # that is left is a valid optional field
        for fieldName, expectedValue in candidate.items():
            if fieldName in self.optional_dict.keys():
                self._check_field(fieldName,
                              candidate[fieldName],
                              self.optional_dict[fieldName],
                              candidate_fields,
                              errors, warnings, False)
            else:
                errors.append('Unexpected field "' + fieldName + '" found.')
                continue


        return errors, warnings

def _validateFile(input_file, ingestion_fields, max_errors = -1, ):
    errors = []
    warnings = []
    lineCount = 0
    stoppedEarly = False
    reader = safe_file_reader(input_file)
    try:
        for lineCount, line in enumerate(reader):

            if lineCount and not lineCount % 10000:
                print "Processed %s lines" % lineCount
                
            if max_errors > 0 and len(errors) >= max_errors:
                lineCount -= 1 # didn't actually process this line
                stoppedEarly = True
                break
            try:
                candidate = json.loads(line)
            except ValueError, e:
                errors.append(
                    'Line ' + str(lineCount + 1) + ': Found invalid JSON: ' + str(e) )
                continue
            
            validateErrors, warns = ingestion_fields.validate(candidate, required=True)
            if len(validateErrors) > 0:
                errors.append(
                    'Line ' + str(lineCount + 1) +
                    ': Found valid JSON which does not match expected schema:' +
                    '\n\t' + '\n\t'.join(validateErrors))
           
            for warn in warns:
                print 'line %d: warning - %s' %(lineCount, warn)
                warnings.append(warn)


    except UnicodeDecodeError, e:
        errors.append(
            'Line ' + str(lineCount + 1) +
            ': Found invalid UTF-8 characters.  ' +
            'Check the encoding of the input file: ' + str(e))      

    return errors, warnings, lineCount + 1, stoppedEarly

# FieldChecker representing the expected JSON structure for a song / track ingestion
track_fields = DictFieldChecker(
    [
        Field('type', unicode()),
        Field('id', unicode()),
        Field('name', unicode()),
        Field('artist', DictFieldChecker(
            [
                Field('id', unicode()), 
                Field('name', unicode()),
            ],  [],  []
          )
        )
    ]
    ,
    [
        Field('extras', DictTypeChecker(unicode(), object())),
        Field('takedown', bool()),
        Field('regions', ListTypeChecker(unicode()), disallowedFields=['regions_add', 'regions_delete']),
        Field('regions_add', ListTypeChecker(unicode()), disallowedFields=['regions']),
        Field('regions_delete', ListTypeChecker(unicode()), disallowedFields=['regions']),
        Field('ISRC', unicode()),
        Field('release_year', int()),
        Field('audio_url', unicode()),
        Field('release', DictFieldChecker(
            [ 
                Field('id', unicode()),
                Field('name', unicode()) 
            ],
            [  
                Field('release_year', int())
            ],  [] 
          )
        )
    ]
    ,  
    [
        Field('published', bool())
    ]
)

# FieldChecker representing the expected JSON structure for an artist ingestion
artist_fields = DictFieldChecker(
    [
        Field('id', unicode()),
        Field('name', unicode()),
    ]
    ,
    [
        Field('extras', DictTypeChecker(unicode(), object())),
        Field('regions', ListTypeChecker(unicode()), disallowedFields=['regions_add', 'regions_delete']),
        Field('regions_add', ListTypeChecker(unicode()), disallowedFields=['regions']),
        Field('regions_delete', ListTypeChecker(unicode()), disallowedFields=['regions']),
        Field('takedown', bool()),
    ]
    ,
    [
        Field('published', bool())
    ]
)

def main():
    usage = "VERSION : " + __version__ + """
python json_validator.py [-h] <json filename> <type> [OPTIONS]
        <json filename> : name of file containing JSON to be validated
        <type> : either 'artist' or 'track'. 

                         
This script will check that an input file matches The Echo Nest's expected
format.  The expected format is a UTF-8 encoded file, containing one
json-encoded line per track or artist, where each line contains the 
expected set of fields.

The expected and required fields for "track" as follows:"""
    usage += track_fields.stringify()
    usage += """

The expected and required fields for "artist" as follows:
    """
    usage += artist_fields.stringify()

    parser = OptionParser(usage=usage)
    parser.add_option('-m', '--max_errors', dest='max_errors', action="store", type="int", default=1000,
        help="optional integer argument specifying maximum number of errors to be reported. Default is to report first 1000 errors.  Passing -1 will report all errors.")    
    
    options, args = parser.parse_args()

    if not args or not len(args) == 2:
        parser.error('Please provide <csv filename> <type>')

    filename = args[0]
    typer = args[1]
    if not typer in ['artist', 'track']:
        parser.error('unable to parse "%s" please proide either "artist" or "track" as the type')

    maxErrors = options.max_errors

    try:
        inputFile = codecs.open(filename, 'r', encoding='utf-8')
    except IOError, e:
        parser.error( 'Can\'t open file: "' + filename + '" for reason: ' + e.strerror )

    fields = track_fields if typer =='track' else artist_fields

    allErrors, allWarns, count, stoppedEarly = _validateFile(inputFile, fields, maxErrors)

    def _plural(num, value):
        return value + ('s' if num != 1 else '')

    for err in allErrors:
        print err

    if stoppedEarly:
        print '\n*** WARNING ***: Error limit reached.  Did not check all lines.  ' \
              'See usage to increase number of reported errors'

    print '\nChecked ' + str(count) + ' ' + _plural(count, 'line') + ', ' + \
        'found ' + _plural(len(allErrors), 'error') + \
        ' on ' + str(len(allErrors)) + \
        ' ' + _plural(len(allErrors), 'line') + ' and found ' + \
         _plural(len(allWarns), 'warning') + ' on ' + str(len(allWarns)) + ' lines'

    if not allErrors:
        print '\nFile is valid to send to The Echo Nest'

    print

if __name__ == '__main__':
    main()
