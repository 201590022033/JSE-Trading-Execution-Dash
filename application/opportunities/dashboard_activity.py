"""Short-lived, local-only dashboard presence; no trading or account state."""
from time import monotonic
from urllib.parse import urlsplit
import re
from flask import Blueprint, jsonify, request

LEASE_SECONDS = 90


def create_dashboard_activity_blueprint(clock=monotonic):
    bp = Blueprint('dashboard_activity', __name__)
    leases = {}

    def result(data, status=200):
        response=jsonify(data); response.headers['Cache-Control']='no-store'
        return response,status

    @bp.route('/api/v1/dashboard/activity',methods=['GET','POST'])
    def activity():
        if request.remote_addr not in ('127.0.0.1','::1'):
            return result({'state':'UNAVAILABLE','active':False},403)
        now=clock()
        for key in [k for k,v in leases.items() if v <= now]: leases.pop(key,None)
        if request.method == 'POST':
            origin=urlsplit(request.headers.get('Origin',''))
            if (origin.scheme not in ('http','https') or origin.netloc != request.host
                    or not request.is_json):
                return result({'state':'INVALID_REQUEST','active':False},403)
            data=request.get_json(silent=True) or {}
            client=data.get('client'); active=data.get('active')
            if not isinstance(client,str) or not re.fullmatch('[a-f0-9]{32}',client) or type(active) is not bool:
                return result({'state':'INVALID_REQUEST','active':False},400)
            if active:
                if client not in leases and len(leases)>=64:
                    return result({'state':'BUSY','active':False},429)
                leases[client]=now+LEASE_SECONDS
            else:
                leases.pop(client,None)
        return result({'state':'AVAILABLE','active':bool(leases),'lease_seconds':LEASE_SECONDS})
    return bp
