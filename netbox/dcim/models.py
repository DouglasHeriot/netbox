from collections import OrderedDict

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, Q, ObjectDoesNotExist

from circuits.models import Circuit
from extras.models import CustomFieldModel, CustomField, CustomFieldValue
from extras.rpc import RPC_CLIENTS
from tenancy.models import Tenant
from utilities.fields import ColorField, NullableCharField
from utilities.managers import NaturalOrderByManager
from utilities.models import CreatedUpdatedModel
from utilities.utils import csv_format

from .fields import ASNField, MACAddressField


RACK_TYPE_2POST = 100
RACK_TYPE_4POST = 200
RACK_TYPE_CABINET = 300
RACK_TYPE_WALLFRAME = 1000
RACK_TYPE_WALLCABINET = 1100
RACK_TYPE_CHOICES = (
    (RACK_TYPE_2POST, '2-post frame'),
    (RACK_TYPE_4POST, '4-post frame'),
    (RACK_TYPE_CABINET, '4-post cabinet'),
    (RACK_TYPE_WALLFRAME, 'Wall-mounted frame'),
    (RACK_TYPE_WALLCABINET, 'Wall-mounted cabinet'),
)

RACK_WIDTH_19IN = 19
RACK_WIDTH_23IN = 23
RACK_WIDTH_CHOICES = (
    (RACK_WIDTH_19IN, '19 inches'),
    (RACK_WIDTH_23IN, '23 inches'),
)

RACK_FACE_FRONT = 0
RACK_FACE_REAR = 1
RACK_FACE_CHOICES = [
    [RACK_FACE_FRONT, 'Front'],
    [RACK_FACE_REAR, 'Rear'],
]

SUBDEVICE_ROLE_PARENT = True
SUBDEVICE_ROLE_CHILD = False
SUBDEVICE_ROLE_CHOICES = (
    (None, 'None'),
    (SUBDEVICE_ROLE_PARENT, 'Parent'),
    (SUBDEVICE_ROLE_CHILD, 'Child'),
)

# Virtual
IFACE_FF_VIRTUAL = 0
# Ethernet
IFACE_FF_100ME_FIXED = 800
IFACE_FF_1GE_FIXED = 1000
IFACE_FF_1GE_GBIC = 1050
IFACE_FF_1GE_SFP = 1100
IFACE_FF_10GE_FIXED = 1150
IFACE_FF_10GE_SFP_PLUS = 1200
IFACE_FF_10GE_XFP = 1300
IFACE_FF_10GE_XENPAK = 1310
IFACE_FF_10GE_X2 = 1320
IFACE_FF_25GE_SFP28 = 1350
IFACE_FF_40GE_QSFP_PLUS = 1400
IFACE_FF_100GE_CFP = 1500
IFACE_FF_100GE_QSFP28 = 1600
# Fibrechannel
IFACE_FF_1GFC_SFP = 3010
IFACE_FF_2GFC_SFP = 3020
IFACE_FF_4GFC_SFP = 3040
IFACE_FF_8GFC_SFP_PLUS = 3080
IFACE_FF_16GFC_SFP_PLUS = 3160
# Serial
IFACE_FF_T1 = 4000
IFACE_FF_E1 = 4010
IFACE_FF_T3 = 4040
IFACE_FF_E3 = 4050
# Stacking
IFACE_FF_STACKWISE = 5000
IFACE_FF_STACKWISE_PLUS = 5050
IFACE_FF_FLEXSTACK = 5100
IFACE_FF_FLEXSTACK_PLUS = 5150
# Other
IFACE_FF_OTHER = 32767

IFACE_FF_CHOICES = [
    [
        'Virtual interfaces',
        [
            [IFACE_FF_VIRTUAL, 'Virtual'],
        ]
    ],
    [
        'Ethernet (fixed)',
        [
            [IFACE_FF_100ME_FIXED, '100BASE-TX (10/100ME)'],
            [IFACE_FF_1GE_FIXED, '1000BASE-T (1GE)'],
            [IFACE_FF_10GE_FIXED, '10GBASE-T (10GE)'],
        ]
    ],
    [
        'Ethernet (modular)',
        [
            [IFACE_FF_1GE_GBIC, 'GBIC (1GE)'],
            [IFACE_FF_1GE_SFP, 'SFP (1GE)'],
            [IFACE_FF_10GE_SFP_PLUS, 'SFP+ (10GE)'],
            [IFACE_FF_10GE_XFP, 'XFP (10GE)'],
            [IFACE_FF_10GE_XENPAK, 'XENPAK (10GE)'],
            [IFACE_FF_10GE_X2, 'X2 (10GE)'],
            [IFACE_FF_25GE_SFP28, 'SFP28 (25GE)'],
            [IFACE_FF_40GE_QSFP_PLUS, 'QSFP+ (40GE)'],
            [IFACE_FF_100GE_CFP, 'CFP (100GE)'],
            [IFACE_FF_100GE_QSFP28, 'QSFP28 (100GE)'],
        ]
    ],
    [
        'FibreChannel',
        [
            [IFACE_FF_1GFC_SFP, 'SFP (1GFC)'],
            [IFACE_FF_2GFC_SFP, 'SFP (2GFC)'],
            [IFACE_FF_4GFC_SFP, 'SFP (4GFC)'],
            [IFACE_FF_8GFC_SFP_PLUS, 'SFP+ (8GFC)'],
            [IFACE_FF_16GFC_SFP_PLUS, 'SFP+ (16GFC)'],
        ]
    ],
    [
        'Serial',
        [
            [IFACE_FF_T1, 'T1 (1.544 Mbps)'],
            [IFACE_FF_E1, 'E1 (2.048 Mbps)'],
            [IFACE_FF_T3, 'T3 (45 Mbps)'],
            [IFACE_FF_E3, 'E3 (34 Mbps)'],
        ]
    ],
    [
        'Stacking',
        [
            [IFACE_FF_STACKWISE, 'Cisco StackWise'],
            [IFACE_FF_STACKWISE_PLUS, 'Cisco StackWise Plus'],
            [IFACE_FF_FLEXSTACK, 'Cisco FlexStack'],
            [IFACE_FF_FLEXSTACK_PLUS, 'Cisco FlexStack Plus'],
        ]
    ],
    [
        'Other',
        [
            [IFACE_FF_OTHER, 'Other'],
        ]
    ],
]

STATUS_ACTIVE = True
STATUS_OFFLINE = False
STATUS_CHOICES = [
    [STATUS_ACTIVE, 'Active'],
    [STATUS_OFFLINE, 'Offline'],
]

CONNECTION_STATUS_PLANNED = False
CONNECTION_STATUS_CONNECTED = True
CONNECTION_STATUS_CHOICES = [
    [CONNECTION_STATUS_PLANNED, 'Planned'],
    [CONNECTION_STATUS_CONNECTED, 'Connected'],
]

# For mapping platform -> NC client
RPC_CLIENT_JUNIPER_JUNOS = 'juniper-junos'
RPC_CLIENT_CISCO_IOS = 'cisco-ios'
RPC_CLIENT_OPENGEAR = 'opengear'
RPC_CLIENT_CHOICES = [
    [RPC_CLIENT_JUNIPER_JUNOS, 'Juniper Junos (NETCONF)'],
    [RPC_CLIENT_CISCO_IOS, 'Cisco IOS (SSH)'],
    [RPC_CLIENT_OPENGEAR, 'Opengear (SSH)'],
]


def order_interfaces(queryset, sql_col, primary_ordering=tuple()):
    """
    Attempt to match interface names by their slot/position identifiers and order according. Matching is done using the
    following pattern:

        {a}/{b}/{c}:{d}

    Interfaces are ordered first by field a, then b, then c, and finally d. Leading text (which typically indicates the
    interface's type) is ignored. If any fields are not contained by an interface name, those fields are treated as
    None. 'None' is ordered after all other values. For example:

        et-0/0/0
        et-0/0/1
        et-0/1/0
        xe-0/1/1:0
        xe-0/1/1:1
        xe-0/1/1:2
        xe-0/1/1:3
        et-0/1/2
        ...
        et-0/1/9
        et-0/1/10
        et-0/1/11
        et-1/0/0
        et-1/0/1
        ...
        vlan1
        vlan10

    :param queryset: The base queryset to be ordered
    :param sql_col: Table and name of the SQL column which contains the interface name (ex: ''dcim_interface.name')
    :param primary_ordering: A tuple of fields which take ordering precedence before the interface name (optional)
    """
    ordering = primary_ordering + ('_id1', '_id2', '_id3', '_id4')
    return queryset.extra(select={
        '_id1': "CAST(SUBSTRING({} FROM '([0-9]+)\/[0-9]+\/[0-9]+(:[0-9]+)?$') AS integer)".format(sql_col),
        '_id2': "CAST(SUBSTRING({} FROM '([0-9]+)\/[0-9]+(:[0-9]+)?$') AS integer)".format(sql_col),
        '_id3': "CAST(SUBSTRING({} FROM '([0-9]+)(:[0-9]+)?$') AS integer)".format(sql_col),
        '_id4': "CAST(SUBSTRING({} FROM ':([0-9]+)$') AS integer)".format(sql_col),
    }).order_by(*ordering)


#
# Sites
#

class SiteManager(NaturalOrderByManager):

    def get_queryset(self):
        return self.natural_order_by('name')


class Site(CreatedUpdatedModel, CustomFieldModel):
    """
    A Site represents a geographic location within a network; typically a building or campus. The optional facility
    field can be used to include an external designation, such as a data center name (e.g. Equinix SV6).
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    tenant = models.ForeignKey(Tenant, blank=True, null=True, related_name='sites', on_delete=models.PROTECT)
    facility = models.CharField(max_length=50, blank=True)
    asn = ASNField(blank=True, null=True, verbose_name='ASN')
    physical_address = models.CharField(max_length=200, blank=True)
    shipping_address = models.CharField(max_length=200, blank=True)
    contact_name = models.CharField(max_length=50, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True, verbose_name="Contact E-mail")
    comments = models.TextField(blank=True)
    custom_field_values = GenericRelation(CustomFieldValue, content_type_field='obj_type', object_id_field='obj_id')

    objects = SiteManager()

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('dcim:site', args=[self.slug])

    def to_csv(self):
        return csv_format([
            self.name,
            self.slug,
            self.tenant.name if self.tenant else None,
            self.facility,
            self.asn,
            self.contact_name,
            self.contact_phone,
            self.contact_email,
        ])

    @property
    def count_prefixes(self):
        return self.prefixes.count()

    @property
    def count_vlans(self):
        return self.vlans.count()

    @property
    def count_racks(self):
        return Rack.objects.filter(site=self).count()

    @property
    def count_devices(self):
        return Device.objects.filter(rack__site=self).count()

    @property
    def count_circuits(self):
        return Circuit.objects.filter(terminations__site=self).count()


#
# Racks
#

class RackGroup(models.Model):
    """
    Racks can be grouped as subsets within a Site. The scope of a group will depend on how Sites are defined. For
    example, if a Site spans a corporate campus, a RackGroup might be defined to represent each building within that
    campus. If a Site instead represents a single building, a RackGroup might represent a single room or floor.
    """
    name = models.CharField(max_length=50)
    slug = models.SlugField()
    site = models.ForeignKey('Site', related_name='rack_groups')

    class Meta:
        ordering = ['site', 'name']
        unique_together = [
            ['site', 'name'],
            ['site', 'slug'],
        ]

    def __unicode__(self):
        return u'{} - {}'.format(self.site.name, self.name)

    def get_absolute_url(self):
        return "{}?group_id={}".format(reverse('dcim:rack_list'), self.pk)


class RackRole(models.Model):
    """
    Racks can be organized by functional role, similar to Devices.
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    color = ColorField()

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "{}?role={}".format(reverse('dcim:rack_list'), self.slug)


class RackManager(NaturalOrderByManager):

    def get_queryset(self):
        return self.natural_order_by('site__name', 'name')


class Rack(CreatedUpdatedModel, CustomFieldModel):
    """
    Devices are housed within Racks. Each rack has a defined height measured in rack units, and a front and rear face.
    Each Rack is assigned to a Site and (optionally) a RackGroup.
    """
    name = models.CharField(max_length=50)
    facility_id = NullableCharField(max_length=30, blank=True, null=True, verbose_name='Facility ID')
    site = models.ForeignKey('Site', related_name='racks', on_delete=models.PROTECT)
    group = models.ForeignKey('RackGroup', related_name='racks', blank=True, null=True, on_delete=models.SET_NULL)
    tenant = models.ForeignKey(Tenant, blank=True, null=True, related_name='racks', on_delete=models.PROTECT)
    role = models.ForeignKey('RackRole', related_name='racks', blank=True, null=True, on_delete=models.PROTECT)
    type = models.PositiveSmallIntegerField(choices=RACK_TYPE_CHOICES, blank=True, null=True, verbose_name='Type')
    width = models.PositiveSmallIntegerField(choices=RACK_WIDTH_CHOICES, default=RACK_WIDTH_19IN, verbose_name='Width',
                                             help_text='Rail-to-rail width')
    u_height = models.PositiveSmallIntegerField(default=42, verbose_name='Height (U)',
                                                validators=[MinValueValidator(1), MaxValueValidator(100)])
    desc_units = models.BooleanField(default=False, verbose_name='Descending units',
                                     help_text='Units are numbered top-to-bottom')
    comments = models.TextField(blank=True)
    custom_field_values = GenericRelation(CustomFieldValue, content_type_field='obj_type', object_id_field='obj_id')

    objects = RackManager()

    class Meta:
        ordering = ['site', 'name']
        unique_together = [
            ['site', 'name'],
            ['site', 'facility_id'],
        ]

    def __unicode__(self):
        return self.display_name

    def get_absolute_url(self):
        return reverse('dcim:rack', args=[self.pk])

    def clean(self):

        # Validate that Rack is tall enough to house the installed Devices
        if self.pk:
            top_device = Device.objects.filter(rack=self).exclude(position__isnull=True).order_by('-position').first()
            if top_device:
                min_height = top_device.position + top_device.device_type.u_height - 1
                if self.u_height < min_height:
                    raise ValidationError({
                        'u_height': "Rack must be at least {}U tall to house currently installed devices.".format(
                            min_height
                        )
                    })

    def to_csv(self):
        return csv_format([
            self.site.name,
            self.group.name if self.group else None,
            self.name,
            self.facility_id,
            self.tenant.name if self.tenant else None,
            self.role.name if self.role else None,
            self.get_type_display() if self.type else None,
            self.width,
            self.u_height,
            self.desc_units,
        ])

    @property
    def units(self):
        if self.desc_units:
            return range(1, self.u_height + 1)
        else:
            return reversed(range(1, self.u_height + 1))

    @property
    def display_name(self):
        if self.facility_id:
            return u"{} ({})".format(self.name, self.facility_id)
        return self.name

    def get_rack_units(self, face=RACK_FACE_FRONT, exclude=None, remove_redundant=False):
        """
        Return a list of rack units as dictionaries. Example: {'device': None, 'face': 0, 'id': 48, 'name': 'U48'}
        Each key 'device' is either a Device or None. By default, multi-U devices are repeated for each U they occupy.

        :param face: Rack face (front or rear)
        :param exclude: PK of a Device to exclude (optional); helpful when relocating a Device within a Rack
        :param remove_redundant: If True, rack units occupied by a device already listed will be omitted
        """

        elevation = OrderedDict()
        for u in self.units:
            elevation[u] = {'id': u, 'name': 'U{}'.format(u), 'face': face, 'device': None}

        # Add devices to rack units list
        if self.pk:
            for device in Device.objects.select_related('device_type__manufacturer', 'device_role')\
                    .annotate(devicebay_count=Count('device_bays'))\
                    .exclude(pk=exclude)\
                    .filter(rack=self, position__gt=0)\
                    .filter(Q(face=face) | Q(device_type__is_full_depth=True)):
                if remove_redundant:
                    elevation[device.position]['device'] = device
                    for u in range(device.position + 1, device.position + device.device_type.u_height):
                        elevation.pop(u, None)
                else:
                    for u in range(device.position, device.position + device.device_type.u_height):
                        elevation[u]['device'] = device

        return [u for u in elevation.values()]

    def get_front_elevation(self):
        return self.get_rack_units(face=RACK_FACE_FRONT, remove_redundant=True)

    def get_rear_elevation(self):
        return self.get_rack_units(face=RACK_FACE_REAR, remove_redundant=True)

    def get_available_units(self, u_height=1, rack_face=None, exclude=list()):
        """
        Return a list of units within the rack available to accommodate a device of a given U height (default 1).
        Optionally exclude one or more devices when calculating empty units (needed when moving a device from one
        position to another within a rack).

        :param u_height: Minimum number of contiguous free units required
        :param rack_face: The face of the rack (front or rear) required; 'None' if device is full depth
        :param exclude: List of devices IDs to exclude (useful when moving a device within a rack)
        """

        # Gather all devices which consume U space within the rack
        devices = self.devices.select_related('device_type').filter(position__gte=1).exclude(pk__in=exclude)

        # Initialize the rack unit skeleton
        units = range(1, self.u_height + 1)

        # Remove units consumed by installed devices
        for d in devices:
            if rack_face is None or d.face == rack_face or d.device_type.is_full_depth:
                for u in range(d.position, d.position + d.device_type.u_height):
                    try:
                        units.remove(u)
                    except ValueError:
                        # Found overlapping devices in the rack!
                        pass

        # Remove units without enough space above them to accommodate a device of the specified height
        available_units = []
        for u in units:
            if set(range(u, u + u_height)).issubset(units):
                available_units.append(u)

        return list(reversed(available_units))

    def get_0u_devices(self):
        return self.devices.filter(position=0)

    def get_utilization(self):
        """
        Determine the utilization rate of the rack and return it as a percentage.
        """
        u_available = len(self.get_available_units())
        return int(float(self.u_height - u_available) / self.u_height * 100)


#
# Device Types
#

class Manufacturer(models.Model):
    """
    A Manufacturer represents a company which produces hardware devices; for example, Juniper or Dell.
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "{}?manufacturer={}".format(reverse('dcim:devicetype_list'), self.slug)


class DeviceType(models.Model, CustomFieldModel):
    """
    A DeviceType represents a particular make (Manufacturer) and model of device. It specifies rack height and depth, as
    well as high-level functional role(s).

    Each DeviceType can have an arbitrary number of component templates assigned to it, which define console, power, and
    interface objects. For example, a Juniper EX4300-48T DeviceType would have:

      * 1 ConsolePortTemplate
      * 2 PowerPortTemplates
      * 48 InterfaceTemplates

    When a new Device of this type is created, the appropriate console, power, and interface objects (as defined by the
    DeviceType) are automatically created as well.
    """
    manufacturer = models.ForeignKey('Manufacturer', related_name='device_types', on_delete=models.PROTECT)
    model = models.CharField(max_length=50)
    slug = models.SlugField()
    part_number = models.CharField(max_length=50, blank=True, help_text="Discrete part number (optional)")
    u_height = models.PositiveSmallIntegerField(verbose_name='Height (U)', default=1)
    is_full_depth = models.BooleanField(default=True, verbose_name="Is full depth",
                                        help_text="Device consumes both front and rear rack faces")
    is_console_server = models.BooleanField(default=False, verbose_name='Is a console server',
                                            help_text="This type of device has console server ports")
    is_pdu = models.BooleanField(default=False, verbose_name='Is a PDU',
                                 help_text="This type of device has power outlets")
    is_network_device = models.BooleanField(default=True, verbose_name='Is a network device',
                                            help_text="This type of device has network interfaces")
    subdevice_role = models.NullBooleanField(default=None, verbose_name='Parent/child status',
                                             choices=SUBDEVICE_ROLE_CHOICES,
                                             help_text="Parent devices house child devices in device bays. Select "
                                                       "\"None\" if this device type is neither a parent nor a child.")
    comments = models.TextField(blank=True)
    custom_field_values = GenericRelation(CustomFieldValue, content_type_field='obj_type', object_id_field='obj_id')

    class Meta:
        ordering = ['manufacturer', 'model']
        unique_together = [
            ['manufacturer', 'model'],
            ['manufacturer', 'slug'],
        ]

    def __unicode__(self):
        return self.model

    def __init__(self, *args, **kwargs):
        super(DeviceType, self).__init__(*args, **kwargs)

        # Save a copy of u_height for validation in clean()
        self._original_u_height = self.u_height

    def get_absolute_url(self):
        return reverse('dcim:devicetype', args=[self.pk])

    def clean(self):

        # If editing an existing DeviceType to have a larger u_height, first validate that *all* instances of it have
        # room to expand within their racks. This validation will impose a very high performance penalty when there are
        # many instances to check, but increasing the u_height of a DeviceType should be a very rare occurrence.
        if self.pk is not None and self.u_height > self._original_u_height:
            for d in Device.objects.filter(device_type=self, position__isnull=False):
                face_required = None if self.is_full_depth else d.face
                u_available = d.rack.get_available_units(u_height=self.u_height, rack_face=face_required,
                                                         exclude=[d.pk])
                if d.position not in u_available:
                    raise ValidationError({
                        'u_height': "Device {} in rack {} does not have sufficient space to accommodate a height of "
                                    "{}U".format(d, d.rack, self.u_height)
                    })

        if not self.is_console_server and self.cs_port_templates.count():
            raise ValidationError({
                'is_console_server': "Must delete all console server port templates associated with this device before "
                                     "declassifying it as a console server."
            })

        if not self.is_pdu and self.power_outlet_templates.count():
            raise ValidationError({
                'is_pdu': "Must delete all power outlet templates associated with this device before declassifying it "
                          "as a PDU."
            })

        if not self.is_network_device and self.interface_templates.filter(mgmt_only=False).count():
            raise ValidationError({
                'is_network_device': "Must delete all non-management-only interface templates associated with this "
                                     "device before declassifying it as a network device."
            })

        if self.subdevice_role != SUBDEVICE_ROLE_PARENT and self.device_bay_templates.count():
            raise ValidationError({
                'subdevice_role': "Must delete all device bay templates associated with this device before "
                                  "declassifying it as a parent device."
            })

        if self.u_height and self.subdevice_role == SUBDEVICE_ROLE_CHILD:
            raise ValidationError({
                'u_height': "Child device types must be 0U."
            })

    @property
    def full_name(self):
        return u'{} {}'.format(self.manufacturer.name, self.model)

    @property
    def is_parent_device(self):
        return bool(self.subdevice_role)

    @property
    def is_child_device(self):
        return bool(self.subdevice_role is False)


class ConsolePortTemplate(models.Model):
    """
    A template for a ConsolePort to be created for a new Device.
    """
    device_type = models.ForeignKey('DeviceType', related_name='console_port_templates', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    class Meta:
        ordering = ['device_type', 'name']
        unique_together = ['device_type', 'name']

    def __unicode__(self):
        return self.name


class ConsoleServerPortTemplate(models.Model):
    """
    A template for a ConsoleServerPort to be created for a new Device.
    """
    device_type = models.ForeignKey('DeviceType', related_name='cs_port_templates', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    class Meta:
        ordering = ['device_type', 'name']
        unique_together = ['device_type', 'name']

    def __unicode__(self):
        return self.name


class PowerPortTemplate(models.Model):
    """
    A template for a PowerPort to be created for a new Device.
    """
    device_type = models.ForeignKey('DeviceType', related_name='power_port_templates', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    class Meta:
        ordering = ['device_type', 'name']
        unique_together = ['device_type', 'name']

    def __unicode__(self):
        return self.name


class PowerOutletTemplate(models.Model):
    """
    A template for a PowerOutlet to be created for a new Device.
    """
    device_type = models.ForeignKey('DeviceType', related_name='power_outlet_templates', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    class Meta:
        ordering = ['device_type', 'name']
        unique_together = ['device_type', 'name']

    def __unicode__(self):
        return self.name


class InterfaceTemplateManager(models.Manager):

    def get_queryset(self):
        qs = super(InterfaceTemplateManager, self).get_queryset()
        return order_interfaces(qs, 'dcim_interfacetemplate.name', ('device_type',))


class InterfaceTemplate(models.Model):
    """
    A template for a physical data interface on a new Device.
    """
    device_type = models.ForeignKey('DeviceType', related_name='interface_templates', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    form_factor = models.PositiveSmallIntegerField(choices=IFACE_FF_CHOICES, default=IFACE_FF_10GE_SFP_PLUS)
    mgmt_only = models.BooleanField(default=False, verbose_name='Management only')

    objects = InterfaceTemplateManager()

    class Meta:
        ordering = ['device_type', 'name']
        unique_together = ['device_type', 'name']

    def __unicode__(self):
        return self.name


class DeviceBayTemplate(models.Model):
    """
    A template for a DeviceBay to be created for a new parent Device.
    """
    device_type = models.ForeignKey('DeviceType', related_name='device_bay_templates', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    class Meta:
        ordering = ['device_type', 'name']
        unique_together = ['device_type', 'name']

    def __unicode__(self):
        return self.name


#
# Devices
#

class DeviceRole(models.Model):
    """
    Devices are organized by functional role; for example, "Core Switch" or "File Server". Each DeviceRole is assigned a
    color to be used when displaying rack elevations.
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    color = ColorField()

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "{}?role={}".format(reverse('dcim:device_list'), self.slug)


class Platform(models.Model):
    """
    Platform refers to the software or firmware running on a Device; for example, "Cisco IOS-XR" or "Juniper Junos".
    NetBox uses Platforms to determine how to interact with devices when pulling inventory data or other information by
    specifying an remote procedure call (RPC) client.
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    rpc_client = models.CharField(max_length=30, choices=RPC_CLIENT_CHOICES, blank=True, verbose_name='RPC client')

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "{}?platform={}".format(reverse('dcim:device_list'), self.slug)


class DeviceManager(NaturalOrderByManager):

    def get_queryset(self):
        return self.natural_order_by('name')


class Device(CreatedUpdatedModel, CustomFieldModel):
    """
    A Device represents a piece of physical hardware mounted within a Rack. Each Device is assigned a DeviceType,
    DeviceRole, and (optionally) a Platform. Device names are not required, however if one is set it must be unique.

    Each Device must be assigned to a Rack, although associating it with a particular rack face or unit is optional (for
    example, vertically mounted PDUs do not consume rack units).

    When a new Device is created, console/power/interface components are created along with it as dictated by the
    component templates assigned to its DeviceType. Components can also be added, modified, or deleted after the
    creation of a Device.
    """
    device_type = models.ForeignKey('DeviceType', related_name='instances', on_delete=models.PROTECT)
    device_role = models.ForeignKey('DeviceRole', related_name='devices', on_delete=models.PROTECT)
    tenant = models.ForeignKey(Tenant, blank=True, null=True, related_name='devices', on_delete=models.PROTECT)
    platform = models.ForeignKey('Platform', related_name='devices', blank=True, null=True, on_delete=models.SET_NULL)
    name = NullableCharField(max_length=50, blank=True, null=True, unique=True)
    serial = models.CharField(max_length=50, blank=True, verbose_name='Serial number')
    asset_tag = NullableCharField(max_length=50, blank=True, null=True, unique=True, verbose_name='Asset tag',
                                  help_text='A unique tag used to identify this device')
    rack = models.ForeignKey('Rack', related_name='devices', on_delete=models.PROTECT)
    position = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1)],
                                                verbose_name='Position (U)',
                                                help_text='The lowest-numbered unit occupied by the device')
    face = models.PositiveSmallIntegerField(blank=True, null=True, choices=RACK_FACE_CHOICES, verbose_name='Rack face')
    status = models.BooleanField(choices=STATUS_CHOICES, default=STATUS_ACTIVE, verbose_name='Status')
    primary_ip4 = models.OneToOneField('ipam.IPAddress', related_name='primary_ip4_for', on_delete=models.SET_NULL,
                                       blank=True, null=True, verbose_name='Primary IPv4')
    primary_ip6 = models.OneToOneField('ipam.IPAddress', related_name='primary_ip6_for', on_delete=models.SET_NULL,
                                       blank=True, null=True, verbose_name='Primary IPv6')
    comments = models.TextField(blank=True)
    custom_field_values = GenericRelation(CustomFieldValue, content_type_field='obj_type', object_id_field='obj_id')

    objects = DeviceManager()

    class Meta:
        ordering = ['name']
        unique_together = ['rack', 'position', 'face']

    def __unicode__(self):
        return self.display_name

    def get_absolute_url(self):
        return reverse('dcim:device', args=[self.pk])

    def clean(self):

        # Validate position/face combination
        if self.position and self.face is None:
            raise ValidationError({
                'face': "Must specify rack face when defining rack position."
            })

        try:
            # Child devices cannot be assigned to a rack face/unit
            if self.device_type.is_child_device and self.face is not None:
                raise ValidationError({
                    'face': "Child device types cannot be assigned to a rack face. This is an attribute of the parent "
                            "device."
                })
            if self.device_type.is_child_device and self.position:
                raise ValidationError({
                    'position': "Child device types cannot be assigned to a rack position. This is an attribute of the "
                                "parent device."
                })

            # Validate rack space
            rack_face = self.face if not self.device_type.is_full_depth else None
            exclude_list = [self.pk] if self.pk else []
            try:
                available_units = self.rack.get_available_units(u_height=self.device_type.u_height, rack_face=rack_face,
                                                                exclude=exclude_list)
                if self.position and self.position not in available_units:
                    raise ValidationError({
                        'position': "U{} is already occupied or does not have sufficient space to accommodate a(n) {} "
                                    "({}U).".format(self.position, self.device_type, self.device_type.u_height)
                    })
            except Rack.DoesNotExist:
                pass

        except DeviceType.DoesNotExist:
            pass

    def save(self, *args, **kwargs):

        is_new = not bool(self.pk)

        super(Device, self).save(*args, **kwargs)

        # If this is a new Device, instantiate all of the related components per the DeviceType definition
        if is_new:
            ConsolePort.objects.bulk_create(
                [ConsolePort(device=self, name=template.name) for template in
                 self.device_type.console_port_templates.all()]
            )
            ConsoleServerPort.objects.bulk_create(
                [ConsoleServerPort(device=self, name=template.name) for template in
                 self.device_type.cs_port_templates.all()]
            )
            PowerPort.objects.bulk_create(
                [PowerPort(device=self, name=template.name) for template in
                 self.device_type.power_port_templates.all()]
            )
            PowerOutlet.objects.bulk_create(
                [PowerOutlet(device=self, name=template.name) for template in
                 self.device_type.power_outlet_templates.all()]
            )
            Interface.objects.bulk_create(
                [Interface(device=self, name=template.name, form_factor=template.form_factor,
                           mgmt_only=template.mgmt_only) for template in self.device_type.interface_templates.all()]
            )
            DeviceBay.objects.bulk_create(
                [DeviceBay(device=self, name=template.name) for template in
                 self.device_type.device_bay_templates.all()]
            )

        # Update Rack assignment for any child Devices
        Device.objects.filter(parent_bay__device=self).update(rack=self.rack)

    def to_csv(self):
        return csv_format([
            self.name or '',
            self.device_role.name,
            self.tenant.name if self.tenant else None,
            self.device_type.manufacturer.name,
            self.device_type.model,
            self.platform.name if self.platform else None,
            self.serial,
            self.asset_tag,
            self.rack.site.name,
            self.rack.name,
            self.position,
            self.get_face_display(),
        ])

    @property
    def display_name(self):
        if self.name:
            return self.name
        elif self.position:
            return u"{} ({} U{})".format(self.device_type, self.rack.name, self.position)
        else:
            return u"{} ({})".format(self.device_type, self.rack.name)

    @property
    def identifier(self):
        """
        Return the device name if set; otherwise return the Device's primary key as {pk}
        """
        if self.name is not None:
            return self.name
        return '{{{}}}'.format(self.pk)

    @property
    def primary_ip(self):
        if settings.PREFER_IPV4 and self.primary_ip4:
            return self.primary_ip4
        elif self.primary_ip6:
            return self.primary_ip6
        elif self.primary_ip4:
            return self.primary_ip4
        else:
            return None

    def get_children(self):
        """
        Return the set of child Devices installed in DeviceBays within this Device.
        """
        return Device.objects.filter(parent_bay__device=self.pk)

    def get_rpc_client(self):
        """
        Return the appropriate RPC (e.g. NETCONF, ssh, etc.) client for this device's platform, if one is defined.
        """
        if not self.platform:
            return None
        return RPC_CLIENTS.get(self.platform.rpc_client)


class ConsolePort(models.Model):
    """
    A physical console port within a Device. ConsolePorts connect to ConsoleServerPorts.
    """
    device = models.ForeignKey('Device', related_name='console_ports', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    cs_port = models.OneToOneField('ConsoleServerPort', related_name='connected_console', on_delete=models.SET_NULL,
                                   verbose_name='Console server port', blank=True, null=True)
    connection_status = models.NullBooleanField(choices=CONNECTION_STATUS_CHOICES, default=CONNECTION_STATUS_CONNECTED)

    class Meta:
        ordering = ['device', 'name']
        unique_together = ['device', 'name']

    def __unicode__(self):
        return self.name

    def get_parent_url(self):
        return self.device.get_absolute_url()

    # Used for connections export
    def to_csv(self):
        return csv_format([
            self.cs_port.device.identifier if self.cs_port else None,
            self.cs_port.name if self.cs_port else None,
            self.device.identifier,
            self.name,
            self.get_connection_status_display(),
        ])


class ConsoleServerPortManager(models.Manager):

    def get_queryset(self):
        """
        Include the trailing numeric portion of each port name to allow for proper ordering.
        For example:
            Port 1, Port 2, Port 3 ... Port 9, Port 10, Port 11 ...
        Instead of:
            Port 1, Port 10, Port 11 ... Port 19, Port 2, Port 20 ...
        """
        return super(ConsoleServerPortManager, self).get_queryset().extra(select={
            'name_as_integer': "CAST(substring(dcim_consoleserverport.name FROM '[0-9]+$') AS INTEGER)",
        }).order_by('device', 'name_as_integer')


class ConsoleServerPort(models.Model):
    """
    A physical port within a Device (typically a designated console server) which provides access to ConsolePorts.
    """
    device = models.ForeignKey('Device', related_name='cs_ports', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    objects = ConsoleServerPortManager()

    class Meta:
        unique_together = ['device', 'name']

    def __unicode__(self):
        return self.name

    def get_parent_url(self):
        return self.device.get_absolute_url()


class PowerPort(models.Model):
    """
    A physical power supply (intake) port within a Device. PowerPorts connect to PowerOutlets.
    """
    device = models.ForeignKey('Device', related_name='power_ports', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    power_outlet = models.OneToOneField('PowerOutlet', related_name='connected_port', on_delete=models.SET_NULL,
                                        blank=True, null=True)
    connection_status = models.NullBooleanField(choices=CONNECTION_STATUS_CHOICES, default=CONNECTION_STATUS_CONNECTED)

    class Meta:
        ordering = ['device', 'name']
        unique_together = ['device', 'name']

    def __unicode__(self):
        return self.name

    def get_parent_url(self):
        return self.device.get_absolute_url()

    # Used for connections export
    def csv_format(self):
        return ','.join([
            self.power_outlet.device.identifier if self.power_outlet else None,
            self.power_outlet.name if self.power_outlet else None,
            self.device.identifier,
            self.name,
            self.get_connection_status_display(),
        ])


class PowerOutletManager(models.Manager):

    def get_queryset(self):
        return super(PowerOutletManager, self).get_queryset().extra(select={
            'name_padded': "CONCAT(SUBSTRING(dcim_poweroutlet.name FROM '^[^0-9]+'), "
                           "LPAD(SUBSTRING(dcim_poweroutlet.name FROM '[0-9\/]+$'), 8, '0'))",
        }).order_by('device', 'name_padded')


class PowerOutlet(models.Model):
    """
    A physical power outlet (output) within a Device which provides power to a PowerPort.
    """
    device = models.ForeignKey('Device', related_name='power_outlets', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    objects = PowerOutletManager()

    class Meta:
        unique_together = ['device', 'name']

    def __unicode__(self):
        return self.name

    def get_parent_url(self):
        return self.device.get_absolute_url()


class InterfaceManager(models.Manager):

    def get_queryset(self):
        qs = super(InterfaceManager, self).get_queryset()
        return order_interfaces(qs, 'dcim_interface.name', ('device',))

    def virtual(self):
        return self.get_queryset().filter(form_factor=IFACE_FF_VIRTUAL)

    def physical(self):
        return self.get_queryset().exclude(form_factor=IFACE_FF_VIRTUAL)


class Interface(models.Model):
    """
    A physical data interface within a Device. An Interface can connect to exactly one other Interface via the creation
    of an InterfaceConnection.
    """
    device = models.ForeignKey('Device', related_name='interfaces', on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    form_factor = models.PositiveSmallIntegerField(choices=IFACE_FF_CHOICES, default=IFACE_FF_10GE_SFP_PLUS)
    mac_address = MACAddressField(null=True, blank=True, verbose_name='MAC Address')
    mgmt_only = models.BooleanField(default=False, verbose_name='OOB Management',
                                    help_text="This interface is used only for out-of-band management")
    description = models.CharField(max_length=100, blank=True)

    objects = InterfaceManager()

    class Meta:
        ordering = ['device', 'name']
        unique_together = ['device', 'name']

    def __unicode__(self):
        return self.name

    def get_parent_url(self):
        return self.device.get_absolute_url()

    def clean(self):

        if self.form_factor == IFACE_FF_VIRTUAL and self.is_connected:
            raise ValidationError({
                'form_factor': "Virtual interfaces cannot be connected to another interface or circuit. Disconnect the "
                               "interface or choose a physical form factor."
            })

    @property
    def is_physical(self):
        return self.form_factor != IFACE_FF_VIRTUAL

    @property
    def is_connected(self):
        try:
            return bool(self.circuit_termination)
        except ObjectDoesNotExist:
            pass
        return bool(self.connection)

    @property
    def connection(self):
        try:
            return self.connected_as_a
        except ObjectDoesNotExist:
            pass
        try:
            return self.connected_as_b
        except ObjectDoesNotExist:
            pass
        return None

    @property
    def connected_interface(self):
        try:
            if self.connected_as_a:
                return self.connected_as_a.interface_b
        except ObjectDoesNotExist:
            pass
        try:
            if self.connected_as_b:
                return self.connected_as_b.interface_a
        except ObjectDoesNotExist:
            pass
        return None


class InterfaceConnection(models.Model):
    """
    An InterfaceConnection represents a symmetrical, one-to-one connection between two Interfaces. There is no
    significant difference between the interface_a and interface_b fields.
    """
    interface_a = models.OneToOneField('Interface', related_name='connected_as_a', on_delete=models.CASCADE)
    interface_b = models.OneToOneField('Interface', related_name='connected_as_b', on_delete=models.CASCADE)
    connection_status = models.BooleanField(choices=CONNECTION_STATUS_CHOICES, default=CONNECTION_STATUS_CONNECTED,
                                            verbose_name='Status')

    def clean(self):
        if self.interface_a == self.interface_b:
            raise ValidationError({
                'interface_b': "Cannot connect an interface to itself."
            })

    # Used for connections export
    def to_csv(self):
        return csv_format([
            self.interface_a.device.identifier,
            self.interface_a.name,
            self.interface_b.device.identifier,
            self.interface_b.name,
            self.get_connection_status_display(),
        ])


class DeviceBay(models.Model):
    """
    An empty space within a Device which can house a child device
    """
    device = models.ForeignKey('Device', related_name='device_bays', on_delete=models.CASCADE)
    name = models.CharField(max_length=50, verbose_name='Name')
    installed_device = models.OneToOneField('Device', related_name='parent_bay', on_delete=models.SET_NULL, blank=True,
                                            null=True)

    class Meta:
        ordering = ['device', 'name']
        unique_together = ['device', 'name']

    def __unicode__(self):
        return u'{} - {}'.format(self.device.name, self.name)

    def get_parent_url(self):
        return self.device.get_absolute_url()

    def clean(self):

        # Validate that the parent Device can have DeviceBays
        if not self.device.device_type.is_parent_device:
            raise ValidationError("This type of device ({}) does not support device bays.".format(
                self.device.device_type
            ))

        # Cannot install a device into itself, obviously
        if self.device == self.installed_device:
            raise ValidationError("Cannot install a device into itself.")


class Module(models.Model):
    """
    A Module represents a piece of hardware within a Device, such as a line card or power supply. Modules are used only
    for inventory purposes.
    """
    device = models.ForeignKey('Device', related_name='modules', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', related_name='submodules', blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=50, verbose_name='Name')
    manufacturer = models.ForeignKey('Manufacturer', related_name='modules', blank=True, null=True,
                                     on_delete=models.PROTECT)
    part_id = models.CharField(max_length=50, verbose_name='Part ID', blank=True)
    serial = models.CharField(max_length=50, verbose_name='Serial number', blank=True)
    discovered = models.BooleanField(default=False, verbose_name='Discovered')

    class Meta:
        ordering = ['device__id', 'parent__id', 'name']
        unique_together = ['device', 'parent', 'name']

    def __unicode__(self):
        return self.name

    def get_parent_url(self):
        return reverse('dcim:device_inventory', args=[self.device.pk])
