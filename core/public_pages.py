from django.contrib import messages
from django.contrib.auth.models import User
from django.http import Http404
from django.shortcuts import get_object_or_404,render
from django.utils import timezone
from .models import ContactMessage, DropOffLocation,NewsArticle,Notification
from .forms import ContactMessageForm

COMPANY = {
 'who-we-are': {'title':'Who we are','intro':'FoodLoop Zambia is a surplus food exchange and recovery coordination platform developed by Beaver Technologies Limited.','sections':[('The platform','Food donors publish available items with quantities, conditions and collection deadlines. Verified recipients and recovery partners request suitable listings and coordinate collection with the donor.'),('Recovery pathways','The platform supports human consumption, animal feed and composting or organic recovery. Each listing is assigned to one suitable pathway.'),('Accountability','Organisation verification, role-based access, recorded decisions and confirmation by both collection parties support transparent operations.')]},
 'our-story': {'title':'Our story','intro':'FoodLoop Zambia addresses a coordination problem: surplus food and suitable recipients are often disconnected.','sections':[('The operating problem','Time-sensitive food availability can be difficult to communicate across businesses, institutions and recovery organisations. Quantities, suitability and collection deadlines need to be clear before collection is arranged.'),('The approach','FoodLoop brings listings, requests, donor decisions and collection records into one workspace. It prioritises suitable recovery pathways and measures confirmed outcomes.'),('Development','Beaver Technologies Limited develops the platform around practical organisation workflows, accessible web interfaces and verifiable recovery data.')]},
 'our-teams': {'title':'Our teams','intro':'The FoodLoop operating model brings together technical, verification and recovery-coordination responsibilities.','sections':[('Platform development','Beaver Technologies Limited manages the application, technical maintenance and product development.'),('Organisation verification','Platform administrators review eligibility information, maintain account access and handle reported concerns.'),('Collection coordination','Donors, beneficiary organisations and recovery partners manage listing accuracy, collection arrangements and handover confirmation through their own accounts.')]},
 'partners': {'title':'Partners','intro':'Partnerships support the coordination and appropriate recovery of surplus food.','sections':[('Partner categories','Food businesses and institutions can participate as donors. Eligible organisations can receive food for people, while livestock operators and organic processors can participate through their approved pathways.'),('Partner directory','Partner information will be published here when confirmed.'),('Participate','Register an organisation account to submit your details for verification and take part in the recovery network.')]},
}

def company_page(request,slug):
    if slug not in COMPANY: raise Http404
    return render(request,'company_page.html',{'page':COMPANY[slug],'is_partners':slug=='partners'})

def drop_off_locations(request):
    return render(request,'drop_off_locations.html',{'locations':DropOffLocation.objects.filter(published=True)})

def faq(request):
    return render(request,'faq.html')

def news(request):
    articles=NewsArticle.objects.filter(published=True,published_at__lte=timezone.now())
    return render(request,'news.html',{'articles':articles.filter(category='news'),'success_stories':articles.filter(category='success_story')})

def news_detail(request,slug):
    article=get_object_or_404(NewsArticle,published=True,published_at__lte=timezone.now(),slug=slug)
    return render(request,'news_detail.html',{'article':article})

def contact(request):
    form=ContactMessageForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        enquiry=form.save()
        for admin in User.objects.filter(is_staff=True,is_active=True):
            Notification.objects.create(user=admin,message=f'New website enquiry: {enquiry.subject} — {enquiry.name}'[:240],event_key=f'contact-message-{enquiry.pk}')
        messages.success(request,'Thanks. Your message has been sent to the FoodLoop team.')
        return render(request,'contact.html',{'form':ContactMessageForm(),'sent':True})
    return render(request,'contact.html',{'form':form,'sent':False})
