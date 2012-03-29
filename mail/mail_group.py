# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2010-today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

import datetime as DT
import io
import openerp
import openerp.tools as tools
from osv import osv
from osv import fields
from PIL import Image
import StringIO
import tools
from tools.translate import _

class mail_group(osv.osv):
    """
    A mail_group is a collection of users sharing messages in a discussion
    group. Group users are users that follow the mail group, using the
    subscription/follow mechanism of OpenSocial.
    """
    
    _name = 'mail.group'
    _inherit = ['mail.thread']
    
    def action_group_join(self, cr, uid, ids, context={}):
        return self.message_subscribe(cr, uid, ids, context=context);
    
    def action_group_leave(self, cr, uid, ids, context={}):
        return self.message_unsubscribe(cr, uid, ids, context=context);

    def onchange_photo(self, cr, uid, ids, value, context=None):
        if not value:
            return {'value': {'avatar_big': value, 'avatar': value} }
        return {'value': {'photo_big': value, 'photo': self._photo_resize(cr, uid, value) } }
    
    def _set_photo(self, cr, uid, id, name, value, args, context=None):
        if value:
            return self.write(cr, uid, [id], {'photo_big': value}, context=context)
        else:
            return self.write(cr, uid, [id], {'photo_big': value}, context=context)
    
    def _photo_resize(self, cr, uid, photo, width=128, height=128, context=None):
        image_stream = io.BytesIO(photo.decode('base64'))
        img = Image.open(image_stream)
        img.thumbnail((width, height), Image.ANTIALIAS)
        img_stream = StringIO.StringIO()
        img.save(img_stream, "JPEG")
        return img_stream.getvalue().encode('base64')
        
    def _get_photo(self, cr, uid, ids, name, args, context=None):
        result = dict.fromkeys(ids, False)
        for group in self.browse(cr, uid, ids, context=context):
            if group.photo_big:
                result[group.id] = self._photo_resize(cr, uid, group.photo_big, context=context)
        return result
    
    def is_subscriber(self, cr, uid, ids, name, args, context=None):
        result = {}
        for id in ids:
            result[id] = self.message_is_subscriber(cr, uid, [id], context=context)
        return result
    
    def get_last_month_msg_nbr(self, cr, uid, ids, name, args, context=None):
        result = {}
        message_obj = self.pool.get('mail.message')
        for id in ids:
            lower_date = (DT.datetime.now() - DT.timedelta(days=30)).strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
            result[id] = message_obj.search(cr, uid, ['&', '&', ('model', '=', self._name), ('res_id', 'in', ids), ('date', '>=', lower_date)], count=True, context=context)
        return result
    
    def get_members_nbr(self, cr, uid, ids, name, args, context=None):
        result = {}
        for id in ids:
            result[id] = len(self.message_get_subscribers_ids(cr, uid, [id], context=context))
        return result
    
    def _get_default_photo(self, cr, uid, context=None):
        avatar_path = openerp.modules.get_module_resource('mail', 'static/src/img', 'groupdefault.png')
        return self._photo_resize(cr, uid, open(avatar_path, 'rb').read().encode('base64'), context=context)
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'description': fields.text('Description'),
        'responsible_id': fields.many2one('res.users', string='Responsible',
                            ondelete='set null', required=True, select=1),
        'public': fields.boolean('Public', help='This group is visible by non members'),
        'photo_big': fields.binary('Full-size photo', help='Field holding the full-sized PIL-supported and base64 encoded version of the group image. The photo field is used as an interface for this field.'),
        'photo': fields.function(_get_photo, fnct_inv=_set_photo, string='Photo', type="binary",
            store = {
                'mail.group': (lambda self, cr, uid, ids, c={}: ids, ['photo_big'], 10),
            }, help='Field holding the automatically resized (128x128) PIL-supported and base64 encoded version of the group image.'),
        'joined': fields.function(is_subscriber, type='boolean', string='Joined'),
        'last_month_msg_nbr': fields.function(get_last_month_msg_nbr, type='integer', string='Messages count for last month'),
        'members_nbr': fields.function(get_members_nbr, type='integer', string='Members count'),
    }

    _defaults = {
        'public': True,
        'responsible_id': (lambda s, cr, uid, ctx: uid),
        'photo': _get_default_photo,
    }

mail_group()
